from unittest import TestCase

from RemoteMonitorLibrary import RemoteMonitorLibrary
from RemoteMonitorLibrary.builtin_plugins.atop_plugin import aTop

sys_trace: RemoteMonitorLibrary = None


class TestSystemTraceLibrary(TestCase):
    def test_create_connection(self):
        global sys_trace
        sys_trace = RemoteMonitorLibrary(atop_plugin=aTop)
        print(f"Connection created")

    def test_close_connection(self):
        sys_trace.end_suite()

    def test_close_all_connections(self):
        self.fail()

    def test_start_trace_plugin(self):
        self.fail()

    def test_stop_trace_plugin(self):
        self.fail()

    def test_start_period(self):
        self.fail()

    def test_stop_period(self):
        self.fail()
