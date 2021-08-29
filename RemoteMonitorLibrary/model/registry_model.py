from abc import ABCMeta, abstractmethod
from sqlite3 import IntegrityError
from threading import Event
from typing import Callable, Dict, AnyStr, Tuple, Any

from robot.utils import timestr_to_secs

from RemoteMonitorLibrary.model import Configuration
from RemoteMonitorLibrary.utils import logger
from RemoteMonitorLibrary.utils.sql_engine import insert_sql, select_sql
from RemoteMonitorLibrary.api import services, tools

_REGISTERED = -1
DEFAULT_INTERVAL = 1

DEFAULT_CONNECTION_INTERVAL = 60
DEFAULT_FAULT_TOLERANCE = 10


def _get_register_id():
    global _REGISTERED
    _REGISTERED += 1
    return _REGISTERED


class RegistryModule(metaclass=ABCMeta):
    schema: Dict[AnyStr, Tuple] = {
        'alias': (True, None, str, str),
        'interval': (False, DEFAULT_INTERVAL, timestr_to_secs, (int, float)),
        'fault_tolerance': (False, DEFAULT_FAULT_TOLERANCE, int, int),
        'event': (False, Event(), Event, Event),
        'timeout': (True, DEFAULT_CONNECTION_INTERVAL, timestr_to_secs, (int, float)),
        'level': (False, 'INFO', str, str)
    }

    def __init__(self, plugin_registry, data_handler: Callable, addon_to_schema: Dict[AnyStr, Tuple[bool, Any, Callable, Any]],
                 alias=None, **options):

        self.schema.update(**addon_to_schema)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}

        self._host_id = _get_register_id()
        alias = alias or f"{self.__class__.__name__.lower()}_{self.host_id:02d}"
        self._configuration = Configuration(self.schema, alias=alias, **options)
        self._errors = tools.GlobalErrors()

    @abstractmethod
    def __str__(self):
        raise NotADirectoryError()

    def start(self):
        self._configuration.update({'event': Event()})
        table = services.TableSchemaService().tables.TraceHost
        try:
            services.DataHandlerService().execute(insert_sql(table.name, table.columns), *(None, self.alias))
            self._host_id = services.DataHandlerService().get_last_row_id
        except IntegrityError:
            host_id = services.DataHandlerService().execute(select_sql(table.name, 'HOST_ID', HostName=self.alias))
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

    def _prepare_config(self, **kwargs):
        conf = self.config.clone()
        tail = conf.update(**kwargs)
        return conf, tail

    def plugin_start(self, plugin_name, *args, **options):
        plugin_conf, tail = self._prepare_config(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin.affiliated_module() == type(self), f"Module '{plugin_name}' not affiliated with module '{self}'"
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

    def get_plugin(self, plugin_name, **options):
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

    @property
    def alias(self):
        return self.config.parameters.alias

    @property
    def event(self):
        return self.config.parameters.event

    @property
    def config(self):
        return self._configuration

    @property
    def active_plugins(self):
        return self._active_plugins

    @property
    def host_id(self):
        return self._host_id
