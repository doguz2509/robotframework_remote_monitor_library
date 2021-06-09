from RemoteMonitorLibrary.utils.logger_helper import logger
from robot.errors import HandlerExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.model import TestCase
from robot.running import TestSuite

from RemoteMonitorLibrary.api.tools import GlobalErrors

ALLOWED_HOOKS = ['start_suite', 'end_suite', 'start_test', 'end_test']


class Hook:
    def __init__(self, kw, *args):
        self._kw = kw
        self._args = args

    def __str__(self):
        return self._kw

    def __call__(self):
        try:
            BuiltIn().run_keyword(self._kw, *self._args)
        except HandlerExecutionFailed:
            logger.warn(f"Connections still not ready")


class AutoSignPeriodsListener:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, **kwargs):
        self.ROBOT_LIBRARY_LISTENER = self

        self._hooks = {}

    def _get_hooks_for(self, hook):
        return self._hooks.get(hook, [])

    def register(self, hook, kw, *args):
        assert hook in ALLOWED_HOOKS, f"Hook '{hook}' not allowed"
        self._hooks.setdefault(hook, []).append(Hook(kw, *args))
        logger.info(f"Keyword '{kw}' successfully registered")

    def unregister(self, hook, kw):
        assert hook in ALLOWED_HOOKS, f"Hook '{hook}' not allowed"

        h = [h for h in self._hooks.get(hook, []) if f"{h}" == h]
        assert len(h) == 0, f"Keyword '{kw}' not registered in '{hook}' scope"
        self._hooks.get(hook, []).remove(h[0])
        logger.info(f"Keyword '{kw}' successfully unregistered")

    def start_suite(self, suite: TestSuite, data):
        for cb in self._get_hooks_for('start_suite'):
            cb()

    def end_suite(self, suite, data):
        for cb in self._get_hooks_for('end_suite'):
            cb()

    def start_test(self, test: TestCase, data):
        for cb in self._get_hooks_for('start_test'):
            cb()

    def end_test(self, test: TestCase, data):
        for cb in self._get_hooks_for('end_test'):
            cb()


class StopOnGlobalErrorListener:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self.ROBOT_LIBRARY_LISTENER = self

    @staticmethod
    def end_test(data, test):
        if len(GlobalErrors()) > 0:
            test.status = 'FAIL'
            test.message = "{}\n{}".format(test.message, '\n\t'.join([f"{e}" for e in GlobalErrors()]))
            BuiltIn().fatal_error(test.message)
