from typing import AnyStr

from system_trace.model.api import PlugIn


class aTopPlugIn(PlugIn):
    @property
    def command(self):
        pass

    def __call__(self):
        pass

    def parse(self, command_output):
        pass

    @property
    def table_schema(self) -> AnyStr:
        pass

    @property
    def table_name(self):
        pass