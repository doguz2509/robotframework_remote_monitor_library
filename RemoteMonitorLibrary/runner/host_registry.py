from collections import Callable
from threading import Event

from robot.api import logger
from robot.utils.connectioncache import ConnectionCache

from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.utils import Singleton, Logger
from RemoteMonitorLibrary.utils.sql_engine import insert_sql


class HostModule:
    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, certificate=None, timeout=None):
        self._configuration = Configuration(alias=alias or f"{username}@{host}:{port}",
                                            host=host, username=username, password=password,
                                            port=port, certificate=certificate, event=None,
                                            timeout=timeout)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}
        self._host_id = -1
        self._errors = GlobalErrors()

    @property
    def host_id(self):
        return self._host_id

    @property
    def config(self):
        return self._configuration

    @property
    def alias(self):
        return self.config.parameters.alias

    def __str__(self):
        return self.config.parameters.host

    @property
    def event(self):
        return self.config.parameters.event

    @property
    def active_plugins(self):
        return self._active_plugins

    def start(self):
        self._configuration.update({'event': Event()})
        table = db.TableSchemaService().tables.TraceHost
        db.DataHandlerService().execute(insert_sql(table.name, table.columns), *(None, self.alias))

        self._host_id = db.DataHandlerService().get_last_row_id

    def stop(self):
        try:
            assert self.event
            self.event.set()
            Logger().debug(f"Terminating {self.alias}")
            self._configuration.update({'event': None})
            active_plugins = list(self._active_plugins.keys())
            while len(active_plugins) > 0:
                plugin = active_plugins.pop(0)
                self.plugin_terminate(plugin)
            # self._control_th.join()
        except AssertionError:
            logger.warn(f"Session '{self.alias}' not started yet")
        else:
            Logger().info(f"Session '{self.alias}' stopped", console=True)

    def plugin_start(self, plugin_name, *args, **options):
        plugin_conf = self.config.clone()
        tail = plugin_conf.update(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        try:
            assert plugin, f"Plugin '{plugin_name}' not registered"
            plugin = plugin(plugin_conf.parameters, self._data_handler, host_id=self.host_id, *args, **tail)
        except Exception as e:
            assert "Cannot create plugin instance '{}, args={}, parameters={}, options={}'".format(
                plugin_name,
                ', '.join([f"{a}" for a in args]),
                ', '.join([f"{k}={v}" for k, v in plugin_conf.parameters.items()]),
                ', '.join([f"{k}={v}" for k, v in tail.items()])
            )
        else:
            plugin.start()
            self._active_plugins[hash(plugin)] = plugin

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
                    plugin.stop()
                    assert plugin.iteration_counter > 0
                except AssertionError:
                    logger.warn(f"Plugin '{plugin}' didn't got monitor data during execution")
        except (AssertionError, IndexError) as e:
            logger.info(f"Plugin '{plugin_name}' raised error: {type(e).__name__}: {e}")
        else:
            logger.info(f"PlugIn '{plugin_name}' gracefully stopped")


@Singleton
class HostRegistryCache(ConnectionCache):
    def __init__(self):
        super().__init__('No stored connection found')

    def clear_all(self, closer_method='stop'):
        for conn in self._connections:
            Logger().info(f"Clear {conn}")
            getattr(conn, closer_method)()

    close_all = clear_all

    def stop_current(self):
        self.current.stop()

    def clear_current(self):
        self.stop_current()
        module = self.current

        current_index = self._connections.index(module)
        self._connections.pop(current_index)
        del self._aliases[module.alias]
        last_connection = len(self._connections) - 1

        self.current = self.get_connection(last_connection) if last_connection > 0 else self._no_current
