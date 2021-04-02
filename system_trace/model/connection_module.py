from collections import Callable
from threading import Event

from robot.api import logger

from system_trace.model.configuration import Configuration
from system_trace.utils import Logger


class ConnectionModule:
    _module_counter = 0

    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, certificate=None):
        self._module_counter += 1
        self._index = self._module_counter
        self._configuration = Configuration(alias=alias or f"{username}@{host}:{port}",
                                            host=host, username=username, password=password,
                                            port=port, certificate=certificate, event=None)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}

    @property
    def config(self):
        return self._configuration

    @property
    def index(self):
        return self._index

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
            Logger().warning(f"Session '{self.alias}' not started yet")

    def plugin_start(self, plugin_name, **options):
        plugin_conf = self.config.clone()
        plugin_conf.update(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not registered"
        plugin = plugin(plugin_conf.parameters, self._data_handler)
        plugin.start()
        # plugin._persistent_worker()
        self._active_plugins[plugin.name] = plugin
        logger.info(f"PlugIn '{plugin_name}' started")

    def plugin_terminate(self, plugin_name):
        plugin = self._active_plugins.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not active"
        plugin.stop()
        logger.info(f"PlugIn '{plugin_name}' gracefully stopped")
