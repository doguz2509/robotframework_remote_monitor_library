from abc import ABCMeta, abstractmethod
from typing import Callable, Dict, AnyStr, Tuple, Any

from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model import Configuration

_REGISTERED = -1


def get_register_id():
    global _REGISTERED
    _REGISTERED += 1
    return _REGISTERED


class RegistryModule(metaclass=ABCMeta):

    def __init__(self, plugin_registry, data_handler: Callable, schema: Dict[AnyStr, Tuple[bool, Any, Callable, Any]],
                 alias=None, **options):
        self._configuration = Configuration(schema, alias=alias, **options)
        self._plugin_registry = plugin_registry
        self._data_handler = data_handler
        self._active_plugins = {}

        self._host_id = get_register_id()
        self._errors = GlobalErrors()

    @abstractmethod
    def __str__(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def plugin_start(self, plugin_name, args, options):
        pass

    @abstractmethod
    def get_plugin(self, plugin_name, options):
        pass

    @abstractmethod
    def plugin_terminate(self, plugin_name, options):
        pass

    @abstractmethod
    def pause_plugins(self):
        pass

    @abstractmethod
    def resume_plugins(self):
        pass

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
