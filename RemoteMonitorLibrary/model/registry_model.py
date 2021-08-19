from abc import ABCMeta, abstractmethod
from threading import Event
from typing import Callable, Dict, AnyStr, Tuple, Any

from robot.utils import timestr_to_secs

from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model import Configuration

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
        alias = alias or self.__class__.__name__.lower()
        self._configuration = Configuration(self.schema, alias=f"{alias}_{self.host_id:02d}", **options)
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
