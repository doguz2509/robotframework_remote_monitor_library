from enum import Enum
from typing import Iterable, Callable

from RemoteMonitorLibrary.model import db_schema as model
from RemoteMonitorLibrary.model.chart_abstract import ChartAbstract


class _ExecutionResult:
    def __init__(self, **kwargs):
        self._return_stdout = kwargs.get('return_stdout', True)
        self._return_stderr = kwargs.get('return_stderr', False)
        self._return_rc = kwargs.get('return_rc', False)

    @property
    def expected_result_len(self):
        _len = 0
        if self._return_stdout:
            _len += 1
        if self._return_stderr:
            _len += 1
        if self._return_rc:
            _len += 1
        return _len

    @property
    def result_index(self):
        _index = {}
        if self._return_stdout:
            yield 'stdout', 0
            if self._return_stderr:
                yield 'stderr', 1
                if self._return_rc:
                    yield 'rc', 2
            else:
                if self._return_rc:
                    yield 'rc', 1
        else:
            if self._return_stderr:
                yield 'stderr', 0
                if self._return_rc:
                    yield 'rc', 1
            else:
                if self._return_rc:
                    yield 'rc', 0

    def __call__(self, result):
        if not isinstance(result, (tuple, list)):
            result = [result]

        assert len(result) == self.expected_result_len, \
            f"Result not match expected elements: {result} [Expected: {self.expected_result_len}]"

        for k, index in dict(self.result_index).items():
            yield k, result[index]


class Parser:
    def __init__(self, **parameters):
        """

        :param parameters:
        """
        self.host_id = parameters.pop('host_id')
        self.table = parameters.pop('table')
        self._data_handler = parameters.pop('data_handler')
        self.counter = parameters.pop('counter', None)
        self._options = parameters

    @property
    def options(self):
        return self._options

    def data_handler(self, data):
        if self.counter is not None:
            self.counter += 1
        self._data_handler(data)

    def __call__(self, output: dict) -> bool:
        raise NotImplementedError()

    def __str__(self):
        return self.__class__.__name__


class FlowCommands(Enum):
    Setup = 'setup'
    Command = 'periodic_commands'
    Teardown = 'teardown'


class plugin_runner_abstract:
    def __init__(self, data_handler: Callable, *args, **kwargs):
        self._stored_shell = {}
        self.variables = {}
        self._data_handler = data_handler
        self._name = kwargs.pop('name', self.__class__.__name__)
        self._iteration_counter = 0
        self._host_id = kwargs.pop('host_id', None)
        self._user_args = args
        self._user_options = kwargs
        self._commands = {}

    def set_commands(self, type_: FlowCommands, *commands):
        self._commands.setdefault(type_, []).extend(commands)

    def store_variable(self, variable_name):
        def _(value):
            self.variables[variable_name] = value
        return _

    @property
    def name(self):
        return self._name

    @property
    def args(self):
        return self._user_args

    @property
    def options(self):
        return self._user_options

    @property
    def host_id(self):
        return self._host_id

    @property
    def iteration_counter(self) -> int:
        return self._iteration_counter

    @iteration_counter.setter
    def iteration_counter(self, add):
        self._iteration_counter += add

    @property
    def data_handler(self):
        self.iteration_counter += 1
        return self._data_handler

    @property
    def flow_type(self):
        return FlowCommands

    @property
    def setup(self):
        return self._commands.get(FlowCommands.Setup, ())

    @property
    def periodic_commands(self):
        return self._commands.get(FlowCommands.Command, ())

    @property
    def teardown(self):
        return self._commands.get(FlowCommands.Teardown, ())

    def inside_host(self):
        raise NotImplementedError()

    def login(self):
        raise NotImplementedError()

    def exit(self):
        raise NotImplementedError()


class plugin_integration_abstract(object):

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return []

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return []

    # @staticmethod
    # def to_json():
    #     return {
    #         'tables': [t.name for t in plugin_integration_abstract.affiliated_tables()],
    #         'charts': [{chart.__class__.__name__: chart.sections for chart in plugin_integration_abstract.affiliated_charts()}]
    #     }

    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{id(self)}")

