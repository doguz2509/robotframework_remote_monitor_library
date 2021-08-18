from RemoteMonitorLibrary.model.registry_model import RegistryModule


class WebAPI_Module(RegistryModule):
    def __init__(self, plugin_registry, data_handler, alias=None, **options):
        super().__init__(plugin_registry, data_handler, alias=alias, **options)

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
