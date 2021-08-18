import os
from threading import Event
from unittest import TestCase

from robot.utils import DotDict

from RemoteMonitorLibrary.api import plugins
from RemoteMonitorLibrary.api.db import *
from RemoteMonitorLibrary.model.runner_model import plugin_runner_abstract
from RemoteMonitorLibrary import plugins
from RemoteMonitorLibrary.utils import load_modules

parameters = DotDict(host='192.168.27.141', username='vagrant', port=22, certificate=None,
                     password='vagrant', interval=10, fault_tolerance=10, alias=None,
                     sudo=True, sudo_password=True,
                     timeout=20, event=Event())


class Test_aTop(TestCase):
    plugin: plugins.aTop = None

    @classmethod
    def setUpClass(cls):
        DataHandlerService().init("./unittests", cls.__name__.lower())
        plugin_modules = load_modules(plugins, base_class=plugin_runner_abstract)
        PlugInService().update(**plugin_modules)
        DataHandlerService().start()
        cls.plugin = plugins.aTop(parameters, DataHandlerService().add_data_unit, host_id='atop')
        cls.plugin.upgrade_plugin('apache', kworker=True)

    def test_01_persistent_worker(self):
        self.plugin._persistent_worker()

    def test_02_non_persistent_worker(self):
        self.plugin._non_persistent_worker()
