import itertools
from datetime import datetime
from threading import Event
from unittest import TestCase
from shutil import rmtree

from RemoteMonitorLibrary.api.services import CacheLines, DataHandlerService


class TestCacheLines(TestCase):
    _event = None
    _data_source = None
    _lines_count = 0
    _test_start = None
    _location = r'./line_cache'
    _portions = ((0, 20), (10, 30), (20, 40), (30, 60), (50, 70), (60, 80), (70, 90), (80, 100))

    @classmethod
    def setUpClass(cls) -> None:
        rmtree(cls._location, True)
        with open(r'make.txt', 'r') as sr:
            cls._data_source = sr.read()
        data_lines = cls._data_source.splitlines()

        data_lines_len = len(data_lines)
        cls._data_map = {f"{i[0]}%-{i[1]}%": (int(data_lines_len * i[0] / 100), int(data_lines_len * i[1] / 100)) for i in cls._portions}
        cls._data_portions = {k: data_lines[b or None:e or None] for k, (b, e) in cls._data_map.items()}
        cls._lines_count = len(set(itertools.chain(*cls._data_portions.values())))

    @classmethod
    def tearDownClass(cls) -> None:
        DataHandlerService().stop()

    def setUp(self) -> None:
        self._event = Event()
        DataHandlerService().init(self._location, self._testMethodName, False)
        DataHandlerService().start(self._event)
        self._workers = int(self._testMethodName.split('_')[-1])
        self._test_start = datetime.now()

    def tearDown(self) -> None:
        print(f"Test {self._testMethodName} {self._workers} workers - duration: "
              f"{(datetime.now() - self._test_start).total_seconds()}s. [DB: {DataHandlerService().db_file}]")
        DataHandlerService().stop()

    def verify_all_data_inside(self):
        assert DataHandlerService().execute('SELECT COUNT() FROM LinesCache')[0][0] == self._lines_count, f"Data integrity error: "

    def test_upload_01(self):
        for name, portion in self._data_portions.items():
            _start = datetime.now()
            CacheLines().upload('\n'.join(portion), self._workers)
            print(f"\t{name} duration: {(datetime.now() - _start).total_seconds()}s.")
        self.verify_all_data_inside()

    def test_upload_02(self):
        for name, portion in self._data_portions.items():
            _start = datetime.now()
            CacheLines().upload('\n'.join(portion), self._workers)
            print(f"\t{name} duration: {(datetime.now() - _start).total_seconds()}s.")
        self.verify_all_data_inside()

    def test_upload_03(self):
        for name, portion in self._data_portions.items():
            _start = datetime.now()
            CacheLines().upload('\n'.join(portion), self._workers)
            print(f"\t{name} duration: {(datetime.now() - _start).total_seconds()}s.")
        self.verify_all_data_inside()

    def test_upload_04(self):
        for name, portion in self._data_portions.items():
            _start = datetime.now()
            CacheLines().upload('\n'.join(portion), self._workers)
            print(f"\t{name} duration: {(datetime.now() - _start).total_seconds()}s.")
        self.verify_all_data_inside()

    def test_upload_05(self):
        for name, portion in self._data_portions.items():
            _start = datetime.now()
            CacheLines().upload('\n'.join(portion), self._workers)
            print(f"\t{name} duration: {(datetime.now() - _start).total_seconds()}s.")
        self.verify_all_data_inside()

    # def test_upload_10(self):
    #    CacheLines().upload(self._data_source)
    #
    # def test_upload_20(self):
    #    CacheLines().upload(self._data_source)
    #
    # def test_upload_40(self):
    #    CacheLines().upload(self._data_source)
