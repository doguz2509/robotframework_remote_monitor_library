from unittest import TestCase

from system_trace import SystemTraceLibrary
from system_trace.builtin_plugins.atop_plugin import aTopPlugIn

sys_trace: SystemTraceLibrary = None


class TestSystemTraceLibrary(TestCase):
    def test_create_connection(self):
        global sys_trace
        sys_trace = SystemTraceLibrary(atop_plugin=aTopPlugIn)
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
