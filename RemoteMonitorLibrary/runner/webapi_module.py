from robot.utils import is_truthy

from RemoteMonitorLibrary.model.registry_model import *

schema: Dict[AnyStr, Tuple] = {
    'url': (True, None, str, str),
    'user': (True, None, str, str),
    'password': (False, '', str, str),
    'port': (False, 22, int, int),
    'keep_alive': (False, True, is_truthy, (bool, str))
}


class WebAPI_Module(RegistryModule):
    def __init__(self, plugin_registry, data_handler, alias=None, **options):
        super().__init__(plugin_registry, data_handler, schema,
                         alias=alias or "WEB",
                         **options)
        self._session = None
        self._auth_token = ''

    def __str__(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def plugin_start(self, plugin_name, args, options):
        pass

    def get_plugin(self, plugin_name, options):
        pass

    def plugin_terminate(self, plugin_name, options):
        pass

    def pause_plugins(self):
        pass

    def resume_plugins(self):
        pass
