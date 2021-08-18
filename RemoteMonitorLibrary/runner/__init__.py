from enum import Enum

from robot.utils import ConnectionCache

from .chart_generator import generate_charts
from .ssh_runner import SSHLibraryPlugInWrapper
from .ssh_module import SSHHostModule
from .webapi_module import WebAPI_Module
from ..utils import Singleton, logger


class Modules(Enum):
    SSH = SSHHostModule
    WEB = WebAPI_Module


@Singleton
class HostRegistryCache(ConnectionCache):
    def __init__(self):
        super().__init__('No stored connection found')

    def clear_all(self, closer_method='stop'):
        for conn in self._connections:
            logger.info(f"Clear {conn}", also_console=True)
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


__all__ = [
    'HostRegistryCache',
    'generate_charts',
    'SSHLibraryPlugInWrapper',
    'Modules'
]