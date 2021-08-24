from unittest import TestCase

from RemoteMonitorLibrary.api.services import DataHandlerService
from RemoteMonitorLibrary.plugins_modules.time_plugin import TimeParser


class Test_TimeParser(TestCase):

    @classmethod
    def setUpClass(cls):
        DataHandlerService().init(r'./', 'sql_db', True)
        DataHandlerService().start()
        with open(r'./make.txt', 'r') as sr:
            _output = sr.readlines()
            cls._stdout = _output[:1]
            cls._stderr = _output[:-1]

    @classmethod
    def tearDownClass(cls):
        DataHandlerService().stop()

    def test_parser(self):
        p = TimeParser(**dict(stdout=self._stdout, stderr=self._stderr, rc=0))
        print()
