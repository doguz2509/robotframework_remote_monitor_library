from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from threading import RLock, Thread, Event
from time import sleep
from typing import Iterable, Callable, Mapping, AnyStr, Any

from robot.utils import is_truthy, timestr_to_secs

from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model import db_schema as model
from RemoteMonitorLibrary.model.chart_abstract import ChartAbstract
from RemoteMonitorLibrary.model.errors import RunnerError, EmptyCommandSet, PlugInError
from RemoteMonitorLibrary.utils import evaluate_duration
from RemoteMonitorLibrary.utils.logger_helper import logger


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


class Variable:
    def __init__(self):
        self._result = None

    def __call__(self, output):
        raise NotImplementedError

    @property
    def result(self) -> Mapping[AnyStr, Any]:
        return self._result

    @result.setter
    def result(self, value: Mapping[AnyStr, Any]):
        self._result = value


class FlowCommands(Enum):
    Setup = 'setup'
    Command = 'periodic_commands'
    Teardown = 'teardown'


class plugin_runner_abstract:
    def __init__(self, parameters, data_handler: Callable, *args, **kwargs):
        self._stored_shell = {}
        self.variables = {}
        self._data_handler = data_handler
        self._name = kwargs.pop('name', self.__class__.__name__)
        self._iteration_counter = 0
        self._host_id = kwargs.pop('host_id', None)
        self._user_args = args
        self._user_options = kwargs
        self._commands = {}
        self._lock = RLock()
        self._is_logged_in = False
        self.parameters = parameters
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []
        assert self._host_id, "Host ID cannot be empty"
        self._persistent = is_truthy(kwargs.get('persistent', 'yes'))
        self._thread: Thread = None

    @property
    def host_alias(self):
        return self.parameters.alias

    def __repr__(self):
        return f"{self.id}"

    def __str__(self):
        return f"{self.id}::{self.host_alias}"

    @property
    def info(self):
        _str = f"{self.__class__.__name__} on host {self.host_alias} ({self.id}) :"
        for set_ in FlowCommands:
            commands = getattr(self, set_.value, ())
            _str += f"\n{set_.name}:"
            if len(commands) > 0:
                _str += '\n\t{}'.format('\n\t'.join([f"{c}" for c in getattr(self, set_.value, ())]))
            else:
                _str += f' N/A'
        return _str

    def start(self):
        self._set_worker()
        self._thread.start()

    def stop(self, timeout=None):
        timeout = timeout or '20s'
        timeout = timestr_to_secs(timeout)
        self._internal_event.set()
        self._thread.join(timeout)
        self._thread = None

    @property
    def interval(self):
        return self._interval

    @property
    def persistent(self):
        return self._persistent

    @staticmethod
    def normalise_arguments(prefix='return', func=is_truthy, **kwargs):
        for k in kwargs.keys():
            v = kwargs.get(k)
            if k.startswith(prefix):
                kwargs.update({k: func(v)})
        return kwargs

    @staticmethod
    def _normalise_commands(*commands):
        for command in commands:
            if isinstance(command, (list, tuple)):
                for sub_command in command:
                    yield sub_command
            else:
                yield command

    def set_commands(self, type_: FlowCommands, *commands):
        self._commands.setdefault(type_, []).extend(tuple(self._normalise_commands(*commands)))

    @property
    def is_alive(self):
        if self._thread:
            return self._thread.is_alive()
        return False

    def _set_worker(self):
        if self.persistent:
            target = self._persistent_worker
        else:
            target = self._non_persistent_worker
        self._thread = Thread(name=self.id, target=target, daemon=True)

    def _evaluate_tolerance(self):
        if len(self._session_errors) == self._fault_tolerance:
            e = PlugInError(f"{self}",
                            "PlugIn stop invoked; Errors count arrived to limit ({})".format(
                                self.host_alias,
                                self._fault_tolerance,
                            ), *self._session_errors)
            logger.error(f"{e}")
            GlobalErrors().append(e)
            return False
        return True

    @property
    def type(self):
        return f"{self.__class__.__name__}"

    @property
    def id(self):
        return f"{self.type}{f'-{self.name}' if self.type != self.name else ''}"

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

    @contextmanager
    def on_connection(self):
        try:
            with self._lock:
                self.login()

                yield self.content_object
        except RunnerError as e:
            self._session_errors.append(e)
            logger.warn(
                "Non critical error {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                    name=self.host_alias,
                    error=e,
                    real=len(self._session_errors),
                    allowed=self._fault_tolerance,
                ))
        except Exception as e:
            logger.error("Critical Error {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                name=self.host_alias,
                error=e,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
            ))
            GlobalErrors().append(e)
        else:
            if len(self._session_errors):
                logger.debug(
                    f"Host '{self}': Runtime errors occurred during tolerance period cleared")
            self._session_errors.clear()
        finally:
            self.exit()

    @property
    def content_object(self):
        """
        Active executable module
        """
        raise NotImplementedError()

    def login(self):
        raise NotImplementedError()

    def exit(self):
        raise NotImplementedError()

    @property
    def is_continue_expected(self):
        if not self._evaluate_tolerance():
            self.parameters.event.set()
            logger.error(f"Stop requested due of critical error")
            return False
        if self.parameters.event.isSet():
            logger.info(f"Stop requested by external source")
            return False
        if self._internal_event.isSet():
            logger.info(f"Stop requested internally")
            return False
        return True

    def _run_command(self, context_object, flow: Enum):
        total_output = ''
        try:
            flow_values = getattr(self, flow.value)
            if len(flow_values) == 0:
                raise EmptyCommandSet()
            logger.debug(f"Iteration {flow.name} started")
            for i, cmd in enumerate(flow_values):
                run_status = cmd(context_object, **self.parameters)
                total_output += ('\n' if len(total_output) > 0 else '') + "{} [Result: {}]".format(cmd, run_status)
                sleep(0.05)
        except EmptyCommandSet:
            logger.warn(f"Iteration {flow.name} ignored")
        except Exception as e:
            raise RunnerError(f"{self}", f"Command set '{flow.name}' failed", e)
        else:
            logger.info(f"Iteration {flow.name} completed\n{total_output}")

    def _persistent_worker(self):
        logger.info(f"\nPlugIn '{self}' started")
        while self.is_continue_expected:
            with self.on_connection() as context:
                self._run_command(context, self.flow_type.Setup)
                logger.info(f"Host {self}: Setup completed", also_console=True)
                while self.is_continue_expected:
                    try:
                        start_ts = datetime.now()
                        _timedelta = timedelta(seconds=self.parameters.interval) \
                            if self.parameters.interval is not None else timedelta(seconds=0)
                        next_ts = start_ts + _timedelta
                        self._run_command(context, self.flow_type.Command)
                        if self.parameters.interval is not None:
                            evaluate_duration(start_ts, next_ts, self.host_alias)
                        while datetime.now() < next_ts:
                            if not self.is_continue_expected:
                                break
                            sleep(0.5)
                    except RunnerError as e:
                        self._session_errors.append(e)
                        logger.warn(
                            "Error execute on: {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                                name=str(self),
                                error=e,
                                real=len(self._session_errors),
                                allowed=self._fault_tolerance,
                            ))
                    else:
                        if len(self._session_errors):
                            logger.debug(
                                f"Host '{self}': Runtime errors occurred during tolerance period cleared")
                            self._session_errors.clear()
                sleep(2)
                self._run_command(context, self.flow_type.Teardown)
                logger.info(f"Host {self}: Teardown completed", also_console=True)
        sleep(2)
        logger.info(f"PlugIn '{self}' stopped")

    def _non_persistent_worker(self):
        logger.info(f"\nPlugIn '{self}' started")
        with self.on_connection() as ssh:
            self._run_command(ssh, self.flow_type.Setup)
            logger.info(f"Host {self}: Setup completed", also_console=True)
        while self.is_continue_expected:
            with self.on_connection() as ssh:
                # try:
                start_ts = datetime.now()
                _timedelta = timedelta(seconds=self.parameters.interval) \
                    if self.parameters.interval is not None else timedelta(seconds=0)
                next_ts = start_ts + _timedelta
                self._run_command(ssh, self.flow_type.Command)
                if self.parameters.interval is not None:
                    evaluate_duration(start_ts, next_ts, self.host_alias)
            while datetime.now() < next_ts:
                if not self.is_continue_expected:
                    break
                sleep(0.5)
        with self.on_connection() as ssh:
            self._run_command(ssh, self.flow_type.Teardown)
            logger.info(f"Host {self}: Teardown completed", also_console=True)
        logger.info(f"PlugIn '{self}' stopped")


class plugin_integration_abstract(object):
    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return []

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return []

    def upgrade_plugin(self, *args, **kwargs):
        raise NotImplementedError(f"PlugIn '{self.__class__.__name__}' are not support upgrade/downgrade")

    def downgrade_plugin(self, *args, **kwargs):
        raise NotImplementedError(f"PlugIn '{self.__class__.__name__}' are not support upgrade/downgrade")

    @property
    def id(self):
        return f"{self.__class__.__name__}_{id(self)}"

    def __hash__(self):
        return hash(self.id)

