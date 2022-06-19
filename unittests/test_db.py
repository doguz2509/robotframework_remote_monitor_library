import difflib
from threading import Event
from unittest import TestCase

from RemoteMonitorLibrary.api.services import DataHandlerService


class TestDataHandlerService(TestCase):
    _event = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._event = Event()
        DataHandlerService().init(r'./', 'test_db', False)
        DataHandlerService().start(cls._event)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._event.set()

    def test_cache_output(self):
        err = []
        text1 = ('a1\na2\na3', 0)
        text2 = ('a1\na2\na3\na4', 1)
        text3 = ('a1\na3\na4', 2)
        text4 = ('a1\na2\na3\na4\na5', 3)
        text5 = ('a5\na4\na3\na2\na1', 4)
        text6 = ('a1\na2\na3', 0)
        for index, (text, expected_ref) in enumerate([text1, text2, text3, text4, text5, text6]):
            output_ref = DataHandlerService().cache_output(text)
            if output_ref != expected_ref:
                err.append("Test {}; expected output_ref: {}, real: {}\n{}".format(
                    index, expected_ref, output_ref, text))
                continue
            print(f"Test {index}; Out ref: {output_ref}")
        assert len(err) == 0, "following entries wrong:\n{}".format('\n\t'.join(err))

