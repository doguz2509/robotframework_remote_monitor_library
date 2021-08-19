from collections import Callable

import requests

from RemoteMonitorLibrary.api.plugins import Common_PlugInAPI
from RemoteMonitorLibrary.runner import webapi_module
from RemoteMonitorLibrary.utils import logger


class WebAPI_Plugin(Common_PlugInAPI):
    def __init__(self,  parameters, data_handler: Callable, *args, **kwargs):
        super().__init__(parameters, data_handler, *args, **kwargs)
        self._session = None
        self._auth_token: str = ''

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
        return self._session

    @property
    def base_url(self):
        return f"{self.parameters.protocol}://{self.parameters.url}:{self.parameters.port}"

    @property
    def headers(self):
        headers_ = {'Authorization': self._auth_token}
        if self.parameters.keep_alive:
            headers_.update(Connection='keep-alive')
        return headers_

    @staticmethod
    def affiliated_module():
        return webapi_module.WebAPI_Module

    @property
    def content_object(self):
        pass

    def open_connection(self):
        pass

    def close_connection(self):
        pass