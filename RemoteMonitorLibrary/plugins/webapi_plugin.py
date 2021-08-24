from collections import Callable

from RemoteMonitorLibrary.api.plugins import Common_PlugInAPI
from RemoteMonitorLibrary.api.plugins import FlowCommands
from RemoteMonitorLibrary.runner import web_module


class WebAPI_Plugin(Common_PlugInAPI):
    def __init__(self,  parameters, data_handler: Callable, *args, **kwargs):
        super().__init__(parameters, data_handler, *args, **kwargs)
        self._session: web_module.WebBaseSession = kwargs.get('session', None)
        self._path = kwargs.get('path')

        self.set_commands(FlowCommands.Command, self._path)

    @staticmethod
    def affiliated_module():
        return web_module.WEB_Module

    @property
    def content_object(self):
        yield self._session

    def open_connection(self):
        self._session.login()

    def close_connection(self):
        self._session.close()
