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
    def __init__(self, plugin_registry, data_handler: Callable, **options):
        alias = options.get('alias', None) or 'SSH'
        options.update(alias=alias)
        super().__init__(plugin_registry, data_handler, schema, **options)

    def __str__(self):
        return f"{super().__str__()}:{self.config.parameters.host}"






