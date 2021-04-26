from collections import Callable
from threading import Event, Thread, RLock
from time import sleep

from robot.api import logger
from robot.utils.connectioncache import ConnectionCache

from RemoteMonitorLibrary.api.db import TableSchemaService, DataHandlerService
from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.utils import Singleton, Logger
from RemoteMonitorLibrary.utils.collections import tsQueue
from RemoteMonitorLibrary.utils.sql_engine import insert_sql


class _keep_alive(Thread):
    def __init__(self, name, err_list: tsQueue, event=Event()):
        self.event = event
        self.err_list = err_list
        super().__init__(name=name, daemon=True)

    def run(self):
        Logger().info('Keep alive started')
        while not self.event.isSet():
            if len(self.err_list) > 0:
                self.event.set()
                assert len(self.err_list) == 0, \
                    "Following errors cause {} termination:\n\t{}".format(
                        self.name,
                        '\n\t'.join(self.err_list))
            sleep(1)
        Logger().info('Keep alive stop invoked')

    def join(self, timeout=None):
        if self.event:
            self.event.set()
        Logger().info('Keep alive stopped')


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
        self._keep_alive: _keep_alive = None
        self._errors = tsQueue()

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
        DataHandlerService().execute(insert_sql(TableSchemaService().tables.TraceHost.name,
                                                TableSchemaService().tables.TraceHost.columns), *(None, self.alias))

        self._host_id = DataHandlerService().get_last_row_id
        self._keep_alive = _keep_alive(self.alias, self._errors, self.event)
        self._keep_alive.start()

    def stop(self):
        try:
            assert self.event
            self.event.set()
            self._keep_alive.join()
            self._configuration.update({'event': None})
            active_plugins = list(self._active_plugins.keys())
            while len(active_plugins) > 0:
                plugin = active_plugins.pop(0)
                self.plugin_terminate(plugin)
            # self._control_th.join()
        except AssertionError:
            logger.warn(f"Session '{self.alias}' not started yet")

    def plugin_start(self, plugin_name, *args, **options):
        plugin_conf = self.config.clone()
        tail = plugin_conf.update(**options)
        plugin = self._plugin_registry.get(plugin_name, None)
        assert plugin, f"Plugin '{plugin_name}' not registered"
        plugin = plugin(plugin_conf.parameters, self._data_handler, host_id=self.host_id, *args,
                        error_handler=self._errors.put, **tail)
        plugin.start()
        self._active_plugins[hash(plugin)] = plugin
        logger.info(f"PlugIn '{plugin}' started", also_console=True)

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
        err = []
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
