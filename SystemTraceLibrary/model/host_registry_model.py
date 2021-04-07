from collections import Callable
from threading import Event

from robot.api import logger
from robot.utils.connectioncache import NoConnection, ConnectionCache

from SystemTraceLibrary.api.db import TableSchemaService, DataHandlerService
from SystemTraceLibrary.model.configuration import Configuration
from SystemTraceLibrary.utils import Singleton
from SystemTraceLibrary.utils.sql_engine import insert_sql


class HostModule:
    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, certificate=None):
        self._configuration = Configuration(alias=alias or f"{username}@{host}:{port}",
                                            host=host, username=username, password=password,
                                            port=port, certificate=certificate, event=None)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}
        self._host_id = -1

    @property
    def host_id(self):
        return self._host_id

    @property
    def config(self):
        return self._configuration

    @property
    def alias(self):
        return self.config.parameters.alias

    @property
    def event(self):
        return self.config.parameters.event

    @property
    def active_plugins(self):
        return self._active_plugins

    def start(self):
        self._configuration.update({'event': Event()})
        DataHandlerService().execute(insert_sql(TableSchemaService().tables.TraceHost.name,
                                                TableSchemaService().tables.TraceHost.columns), None, self.alias)

        self._host_id = DataHandlerService().get_last_row_id

    def stop(self):
        try:
            assert self.event
            self.event.set()
            self._configuration.update({'event': None})
            active_plugins = list(self._active_plugins.keys())
            while len(active_plugins) > 0:
                plugin = active_plugins.pop(0)
                self.plugin_terminate(plugin)

        except AssertionError:
            logger.warn(f"Session '{self.alias}' not started yet")

    def plugin_start(self, plugin_name, **options):
        plugin_conf = self.config.clone()
        tail = plugin_conf.update(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not registered"
        plugin = plugin(plugin_conf.parameters, self._data_handler, self.host_id, **tail)
        plugin.start()
        logger.info(f"PlugIn '{plugin}' started")
        self._active_plugins[f"{plugin}"] = plugin
        logger.info(f"PlugIn '{plugin_name}' started")

    def plugin_terminate(self, plugin_name):
        plugin = self._active_plugins.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not active"
        plugin.stop()
        logger.info(f"PlugIn '{plugin_name}' gracefully stopped")


@Singleton
class HostRegistryCache(ConnectionCache):
    def __init__(self):
        super().__init__('No stored connection found')

    def clear_all(self):
        super().close_all('stop')

    def close_current(self):
        self.current.stop()

    def clear_current(self):
        self.close_current()
        module = self.current

        current_index = self._connections.index(module)
        self._connections.pop(current_index)
        del self._aliases[module.alias]
        last_connection = len(self._connections) - 1

        self.current = self.get_connection(last_connection) if last_connection > 0 else self._no_current
