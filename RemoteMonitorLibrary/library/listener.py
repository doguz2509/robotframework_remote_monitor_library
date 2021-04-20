from robot.api import logger
from robot.errors import HandlerExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.model import TestCase
from robot.running import TestSuite


class TraceListener:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, **kwargs):
        self.ROBOT_LIBRARY_LISTENER = self
        self._start_suite_kw = kwargs.get('start_suite', None)
        self._end_suite_kw = kwargs.get('end_suite', None)
        self._start_test_kw = kwargs.get('start_test', None)
        self._end_test_kw = kwargs.get('end_test', None)
        self._last_test_name = None

    def start_suite(self, suite: TestSuite, data):
        if self._start_suite_kw:
            try:
                BuiltIn().run_keyword(self._start_suite_kw, suite.name)
            except HandlerExecutionFailed as e:
                logger.warn(f"Connections still not ready")

    def end_suite(self, suite, data):
        try:
            if self._end_suite_kw:
                BuiltIn().run_keyword(self._end_suite_kw, suite.name)
            if self._end_test_kw and self._last_test_name:
                BuiltIn().run_keyword(self._end_test_kw, self._last_test_name)
        except HandlerExecutionFailed as e:
            logger.warn(f"Connections already closed")

    def start_test(self, test: TestCase, data):
        if self._start_test_kw:
            BuiltIn().run_keyword(self._start_test_kw, test.name)
            self._last_test_name = test.name

    def end_test(self, test: TestCase, data):
        if self._end_test_kw:
            BuiltIn().run_keyword(self._end_test_kw, test.name)
            self._last_test_name = None
