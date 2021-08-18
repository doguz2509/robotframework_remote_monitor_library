from sqlite3 import IntegrityError
from threading import Event
from typing import Callable, Dict, AnyStr, Tuple

from robot.utils import timestr_to_secs

from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.model.registry_model import RegistryModule
from RemoteMonitorLibrary.utils.logger_helper import logger
from RemoteMonitorLibrary.utils.sql_engine import insert_sql, select_sql

DEFAULT_INTERVAL = 1
DEFAULT_CONNECTION_INTERVAL = 60
DEFAULT_FAULT_TOLERANCE = 10

schema: Dict[AnyStr, Tuple] = {
    'alias': (True, None, str, str),
    'host': (True, None, str, str),
    'username': (True, None, str, str),
    'password': (False, '', str, str),
    'port': (False, 22, int, int),
    'certificate': (False, None, str, str),
    'interval': (False, DEFAULT_INTERVAL, timestr_to_secs, (int, float)),
    'fault_tolerance': (False, DEFAULT_FAULT_TOLERANCE, int, int),
    'event': (False, Event(), Event, Event),
    'timeout': (True, DEFAULT_CONNECTION_INTERVAL, timestr_to_secs, (int, float))
}


class SSHHostModule(RegistryModule):
    __doc__ = """Create basic host connection module used for trace host
        Last created connection handled as 'current'
        In case tracing required for one host only, alias can be ignored

        Connection arguments:
        - host: IP address, DNS name,
        - username
        - password
        - port          : 22 if omitted
        - certificate   : key file (.pem) Optional

        Extra arguments:
        - alias: 'username@host:port' if omitted
        - timeout       : connection & command timeout
        - log_to_db     : logger will store logs into db (table: log; Will cause db file size size growing)

        Examples:
        |  KW                       |  Host     | Username | Password       | Port  | Alias             | Comments              |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   |       |                   | Default port; No alias |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   | 24    |                   | Custom port; No alias |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   | 24    |  ${my_name}       | Custom port; Alias    |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   |       |  alias=${my_name} | Default port; Alias    |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   |       |  certificate=key_file.pem | Certificate file will be assigned  |

        === Auto start/stop periods ===
        By default keyword `Start period`, `Stop period` assigned for start/end test accordingly following by test name

        Can be overwritten by key value pairs
        | listener method=keyword name

        Where listener are one of:
        | start_suite
        | end_suite
        | start_test
        | end_test
    """

    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, certificate=None, timeout=None, interval=None):
        super().__init__(plugin_registry, data_handler, schema,
                         alias or f"{username}@{host}:{port}",
                         host=host, username=username, password=password,
                         port=port, certificate=certificate, event=None,
                         timeout=timeout, interval=interval)

    def __str__(self):
        return self.config.parameters.host

    def start(self):
        self._configuration.update({'event': Event()})
        table = db.TableSchemaService().tables.TraceHost
        try:
            db.DataHandlerService().execute(insert_sql(table.name, table.columns), *(None, self.alias))
            self._host_id = db.DataHandlerService().get_last_row_id
        except IntegrityError:
            host_id = db.DataHandlerService().execute(select_sql(table.name, 'HOST_ID', HostName=self.alias))
            assert host_id, f"Cannot occur host id for alias '{self.alias}'"
            self._host_id = host_id[0][0]

    def stop(self):
        try:
            assert self.event
            self.event.set()
            logger.debug(f"Terminating {self.alias}")
            self._configuration.update({'event': None})
            active_plugins = list(self._active_plugins.keys())
            while len(active_plugins) > 0:
                plugin = active_plugins.pop(0)
                self.plugin_terminate(plugin)
            # self._control_th.join()
        except AssertionError:
            logger.warn(f"Session '{self.alias}' not started yet")
        else:
            logger.info(f"Session '{self.alias}' stopped")

    def plugin_start(self, plugin_name, *args, **options):
        plugin_conf = self.config.clone()
        tail = plugin_conf.update(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin.affiliated_modules() == type(self), f"Module '{plugin_name}' not affiliated with module '{self}'"
        try:
            assert plugin, f"Plugin '{plugin_name}' not registered"
            plugin = plugin(plugin_conf.parameters, self._data_handler, host_id=self.host_id, *args, **tail)
        except Exception as e:
            raise RuntimeError("Cannot create plugin instance '{}, args={}, parameters={}, options={}'"
                               "\nError: {}".format(plugin_name,
                                                    ', '.join([f"{a}" for a in args]),
                                                    ', '.join([f"{k}={v}" for k, v in plugin_conf.parameters.items()]),
                                                    ', '.join([f"{k}={v}" for k, v in tail.items()]),
                                                    e
                                                    ))
        else:
            plugin.start()
            logger.info(f"\nPlugin {plugin_name} Started\n{plugin.info}", also_console=True)
            self._active_plugins[plugin.id] = plugin

    def get_plugin(self, plugin_name=None, **options):
        res = []
        if plugin_name is None:
            return list(self._active_plugins.values())

        for p in self._active_plugins.values():
            if type(p).__name__ != plugin_name:
                continue
            if len(options) > 0:
                for name, value in options.items():
                    if hasattr(p, name):
                        p_value = getattr(p, name, None)
                        if p_value is None:
                            continue
                        if p_value != value:
                            continue
                    res.append(p)
            else:
                res.append(p)
        return res

    def plugin_terminate(self, plugin_name, **options):
        try:
            plugins_to_stop = self.get_plugin(plugin_name, **options)
            assert len(plugins_to_stop) > 0, f"Plugins '{plugin_name}' not matched in list"
            for plugin in plugins_to_stop:
                try:
                    plugin.stop(timeout=options.get('timeout', None))
                    assert plugin.iteration_counter > 0
                except AssertionError:
                    logger.warn(f"Plugin '{plugin}' didn't got monitor data during execution")
        except (AssertionError, IndexError) as e:
            logger.info(f"Plugin '{plugin_name}' raised error: {type(e).__name__}: {e}")
        else:
            logger.info(f"PlugIn '{plugin_name}' gracefully stopped", also_console=True)

    def pause_plugins(self):
        for name, plugin in self._active_plugins.items():
            try:
                assert plugin is not None
                plugin.stop()
            except AssertionError:
                logger.info(f"Plugin '{name}' already stopped")
            except Exception as e:
                logger.warn(f"Plugin '{name}:{plugin}' pause error: {e}")
            else:
                logger.info(f"Plugin '{name}' paused", also_console=True)

    def resume_plugins(self):
        for name, plugin in self._active_plugins.items():
            try:
                plugin.start()
            except Exception as e:
                logger.warn(f"Plugin '{name}' resume error: {e}")
            else:
                logger.info(f"Plugin '{name}' resumed", also_console=True)


