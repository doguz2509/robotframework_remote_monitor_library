from typing import Callable, Dict, AnyStr, Tuple

from RemoteMonitorLibrary.model.registry_model import RegistryModule

schema: Dict[AnyStr, Tuple] = {
    'host': (True, None, str, str),
    'username': (True, None, str, str),
    'password': (False, '', str, str),
    'port': (False, 22, int, int),
    'certificate': (False, None, str, str),
}


class SSHModule(RegistryModule):
    def __init__(self, plugin_registry, data_handler: Callable, host, username, password,
                 port=None, alias=None, certificate=None, timeout=None, interval=None):
        super().__init__(plugin_registry, data_handler, schema,
                         alias or "SSH",
                         host=host, username=username, password=password,
                         port=port, certificate=certificate, event=None,
                         timeout=timeout, interval=interval)

    def __str__(self):
        return self.config.parameters.host






