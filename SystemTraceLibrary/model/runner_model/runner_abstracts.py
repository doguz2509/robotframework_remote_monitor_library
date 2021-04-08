from enum import Enum
from typing import Iterable, Callable, Any

from SSHLibrary import SSHLibrary

from SystemTraceLibrary.model import schema_model as model
from SystemTraceLibrary.model.chart_model.chart_abstract import ChartAbstract
from SystemTraceLibrary.utils import get_error_info


class Parser:
    def __init__(self, **parameters):
        """

        :param parameters:
        """
        self.host_id = parameters.get('host_id')
        self.table = parameters.get('table')
        self.data_handler = parameters.get('data_handler')

    def __call__(self, *outputs) -> bool:
        raise NotImplementedError()

    def __str__(self):
        return self.__class__.__name__


class Command:
    def __init__(self, method: Callable, command, **kwargs):
        self.repeat = kwargs.pop('repeat', 1)
        self.variable_cb = kwargs.pop('variable_cb', None)
        self.parser: Parser = kwargs.pop('parser', None)
        if self.parser:
            assert isinstance(self.parser, Parser), f"Parser type error [Error type: {type(self.parser).__name__}]"
        self._method = method
        self._command = command
        self._kwargs = kwargs

    @property
    def sudo(self):
        return self._kwargs.get('sudo', False)

    def __str__(self):
        return f"{self._method.__name__}: " \
               f"{', '.join([f'{a}' for a in [self._command] + [f'{k}={v}' for k, v in self._kwargs.items()]])}" \
               f"{'; Parser: '.format(self.parser) if self.parser else ''}"

    def __call__(self, ssh_client: SSHLibrary, *args, **kwargs) -> Any:
        command_kwargs = dict(**self._kwargs)
        command = self._command

        if command_kwargs.get('sudo', False):
            command = f'sudo {command}'
        elif command_kwargs.get('sudo_password', False):
            command = 'echo %s | sudo --stdin --prompt "" %s' % (kwargs.get('sudo_password', None), command)

        try:
            output = self._method(ssh_client, command, **command_kwargs)
            if self.parser:
                return self.parser(*output)
            return output
        except Exception as e:
            f, li = get_error_info()
            error_type = type(e)
            raise error_type(f"{self.__class__.__name__} -> {error_type.__name__}:{e}; File: {f}:{li}")


CommandSet_Type = Iterable[Command]


class plugin_runner_abstract:
    def __init__(self):
        self._stored_shell = {}
        self.variables = {}

    def store_variable(self, variable_name):
        def _(value):
            self.variables[variable_name] = value

        return _

    @property
    def flow_type(self):
        class FlowCommands(Enum):
            Setup = 'setup'
            Command = 'periodic_commands'
            Teardown = 'teardown'

        return FlowCommands

    @property
    def setup(self) -> CommandSet_Type:
        return ()

    @property
    def periodic_commands(self) -> CommandSet_Type:
        return ()

    @property
    def teardown(self) -> CommandSet_Type:
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
