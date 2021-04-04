from enum import Enum
from typing import Iterable

from SystemTraceLibrary.model import schema_model as model
from SystemTraceLibrary.model.chart_model.chart_abstract import ChartAbstract


class Command:
    def __init__(self, command, **kwargs):
        self._command = command
        self.sudo = kwargs.get('sudo', None)
        self.sudo_password = kwargs.get('sudo_password', None)
        self.interactive = kwargs.get('interactive', None)
        self.repeat = kwargs.get('repeat', 1)
        self.variable_cb = kwargs.get('variable_cb', None)
        self.parser = kwargs.get('parser', None)

    @property
    def command(self):
        if self.sudo:
            if self.sudo_password:
                return f'echo {self.sudo_password}|sudo --stdin --prompt "" {self._command}'
            else:
                return f'sudo {self._command}'
        else:
            return self._command

    def __str__(self):
        return f"{self.command} (To repeat {self.repeat} times)[Sudo: {self.sudo}; Interactive: {self.interactive}]"


CommandsType = Iterable[Command]


class plugin_runner_abstract:
    def __init__(self):
        self._stored_shell = {}
        self.variables = {}

    def store_variable(self, variable_name):
        def _(value):
            setattr(self, variable_name, value)

        return _

    @property
    def flow_type(self):
        class FlowCommands(Enum):
            Setup = 'setup'
            Command = 'periodic_commands'
            Teardown = 'teardown'

        return FlowCommands

    @property
    def setup(self) -> CommandsType:
        return ()

    @property
    def periodic_commands(self) -> CommandsType:
        return ()

    @property
    def teardown(self) -> CommandsType:
        return ()

    def __enter__(self):
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError()


class plugin_integration_abstract(object):
    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{id(self)}")

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return []

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return []
