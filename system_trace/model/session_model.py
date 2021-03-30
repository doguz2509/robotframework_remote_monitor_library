from collections import Callable
from threading import Event

from robot.api import logger

from system_trace.utils import Logger
from system_trace.model.configuration import Configuration


session_counter = 0


def _norm_alias(host, username, port, alias=None):
    return alias or f"{username}@{host}:{port}"


class TraceSession:
    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, interval=None,
                 certificate=None,
                 run_as_sudo=False):
        session_id = _norm_alias(host, username, port, alias)
        global session_counter
        session_counter += 1
        index = session_counter
        self._configuration = Configuration(index=index, alias=session_id,
                                            host=host, username=username, password=password,
                                            port=port, certificate=certificate, run_as_sudo=run_as_sudo,
                                            interval=interval, event=None)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}

    @property
    def config(self):
        return self._configuration

    @property
    def id(self):
        return self.config.alias

    @property
    def event(self):
        return self.config.event

    def start(self):
        self._configuration.update({'event': Event()})

    def close(self):
        try:
            assert self.event
            self.event.set()
            self._configuration.update({'event': None})
            active_plugins = list(self._active_plugins.keys())
            while len(active_plugins) > 0:
                plugin = active_plugins.pop(0)
                self.plugin_terminate(plugin)

        except AssertionError:
            Logger().warning(f"Session '{self.id}' not started yet")

    def plugin_start(self, plugin_name, interval=None):
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not registered"
        plugin = plugin()
        plugin.start(self.config.event, interval)
        self._active_plugins[plugin.name] = plugin
        logger.info(f"PlugIn '{plugin_name}' started")

    def plugin_terminate(self, plugin_name):
        plugin = self._active_plugins.pop(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not active"
        plugin.stop()
        logger.info(f"PlugIn '{plugin_name}' gracefully stopped")
