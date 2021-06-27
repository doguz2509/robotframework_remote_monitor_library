from enum import Enum
from typing import Dict, List

from RemoteMonitorLibrary.utils.logger_helper import logger
from robot.errors import HandlerExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.model import TestCase
from robot.running import TestSuite


class AllowedHooks(Enum):
    start_suite = 'start_suite'
    end_suite = 'end_suite'
    start_test = 'start_test'
    end_test = 'end_test'

    @staticmethod
    def get_hooks():
        return ', '.join([n.name for n in AllowedHooks])


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

        self._hooks: Dict[AllowedHooks, List] = {}

    def _get_hooks_for(self, hook: AllowedHooks):
        return self._hooks.get(hook, [])

    def register(self, hook, kw, *args):
        if isinstance(hook, str):
            assert hook in AllowedHooks.get_hooks(), f"Hook '{hook}' must be '{AllowedHooks.get_hooks()}'"
            hook = AllowedHooks[hook]
        self._hooks.setdefault(hook, []).append(Hook(kw, *args))
        logger.info(f"Keyword '{kw}' successfully registered")

    def unregister(self, hook: AllowedHooks, kw):
        assert hook in AllowedHooks.get_hooks(), f"Hook '{hook}' must be '{AllowedHooks.get_hooks()}'"
        h = [h for h in self._hooks.get(hook, []) if f"{h}" == h]
        assert len(h) == 0, f"Keyword '{kw}' not registered in '{hook}' scope"
        self._hooks.get(hook, []).remove(h[0])
        logger.info(f"Keyword '{kw}' successfully unregistered")

    def start_suite(self, suite: TestSuite, data):
        for cb in self._get_hooks_for(AllowedHooks.start_suite):
            cb()

    def end_suite(self, suite, data):
        for cb in self._get_hooks_for(AllowedHooks.end_suite):
            cb()

    def start_test(self, test: TestCase, data):
        for cb in self._get_hooks_for(AllowedHooks.start_test):
            cb()

    def end_test(self, test: TestCase, data):
        for cb in self._get_hooks_for(AllowedHooks.end_test):
            cb()
