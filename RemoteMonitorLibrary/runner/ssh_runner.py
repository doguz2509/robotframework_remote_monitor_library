from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Event, Thread, Timer
from time import sleep
from typing import Callable, Any

from SSHLibrary import SSHLibrary
from robot.utils import DotDict, is_truthy, timestr_to_secs

from RemoteMonitorLibrary.model.errors import PlugInError, RunnerError, EmptyCommandSet
from RemoteMonitorLibrary.model.runner_model import plugin_runner_abstract, _ExecutionResult, Parser
from RemoteMonitorLibrary.utils import Logger, get_error_info, evaluate_duration

SSHLibraryArgsMapping = {
    SSHLibrary.execute_command.__name__: {'return_stdout': (is_truthy, True),
                                          'return_stderr': (is_truthy, False),
                                          'return_rc': (is_truthy, False), 'sudo': (is_truthy, False),
                                          'sudo_password': (str, None), 'timeout': (timestr_to_secs, None),
                                          'output_during_execution': (is_truthy, False),
                                          'output_if_timeout': (is_truthy, False),
                                          'invoke_subsystem': (is_truthy, False),
                                          'forward_agent': (is_truthy, False)},
    SSHLibrary.start_command.__name__: {'sudo': (is_truthy, False),
                                        'sudo_password': (str, None),
                                        'invoke_subsystem': (is_truthy, False),
                                        'forward_agent': (is_truthy, False)},
    SSHLibrary.write.__name__: {'text': (str, None),
                                'loglevel': (str, 'INFO')},
    SSHLibrary.read_command_output.__name__: {'return_stdout': (is_truthy, True),
                                              'return_stderr': (is_truthy, False),
                                              'return_rc': (is_truthy, False), 'sudo': (is_truthy, False),
                                              'timeout': (timestr_to_secs, None)}
}


def _normalize_method_arguments(method_name, **kwargs):
    assert method_name in SSHLibraryArgsMapping.keys(), f"Method {method_name} not supported"
    for name, value in kwargs.items():
        assert name in SSHLibraryArgsMapping.get(method_name, []).keys(), \
            f"Argument '{name}' not supported for '{method_name}'"
        arg_type, arg_default = SSHLibraryArgsMapping.get(method_name).get(name)
        new_value = arg_type(value) if value else arg_default
        yield name, new_value


def extract_method_arguments(method_name, **kwargs):
    assert method_name in SSHLibraryArgsMapping.keys(), f"Method {method_name} not supported"
    return {name: value for name, value in kwargs.items() if name in SSHLibraryArgsMapping.get(method_name, []).keys()}


class SSHLibraryCommand:
    def __init__(self, method: Callable, command, **user_options):
        self.variable_cb = user_options.pop('variable_cb', None)
        self.parser: Parser = user_options.pop('parser', None)
        self._sudo_expected = is_truthy(user_options.pop('sudo', False))
        self._sudo_password_expected = is_truthy(user_options.pop('sudo_password', False))
        self._start_in_folder = user_options.pop('start_in_folder', None)
        self._ssh_options = dict(_normalize_method_arguments(method.__name__, **user_options))
        self._result_template = _ExecutionResult(**self._ssh_options)
        if self.parser:
            assert isinstance(self.parser, Parser), f"Parser type error [Error type: {type(self.parser).__name__}]"
        self._method = method
        self._command = command

    @property
    def command_template(self):
        _command = f'cd {self._start_in_folder}; ' if self._start_in_folder else ''

        if self._sudo_password_expected:
            _command += f'echo {{password}} | sudo --stdin --prompt "" {self._command}'
        elif self._sudo_expected:
            _command += f'sudo {self._command}'
        else:
            _command += self._command
        return _command

    def __str__(self):
        return f"{self._method.__name__}: " \
               f"{', '.join([f'{a}' for a in [self._command] + [f'{k}={v}' for k, v in self._ssh_options.items()]])}" \
               f"{'; Parser: '.format(self.parser) if self.parser else ''}"

    def __call__(self, ssh_client: SSHLibrary, **runtime_options) -> Any:
        try:
            if self._command is not None:
                command = self.command_template.format(**runtime_options)
                output = self._method(ssh_client, command, **self._ssh_options)
            else:
                output = self._method(ssh_client, **self._ssh_options)
            if self.parser:
                return self.parser(dict(self._result_template(output)))
            return output
        except Exception as e:
            f, li = get_error_info()
            error_type = type(e)
            raise error_type(f"{self.__class__.__name__} -> {error_type.__name__}:{e}; File: {f}:{li}")


class SSHLibraryPlugInWrapper(plugin_runner_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, *user_args, **user_options):
        self._sudo_expected = is_truthy(user_options.pop('sudo', False))
        self._sudo_password_expected = is_truthy(user_options.pop('sudo_password', False))
        super().__init__(data_handler, *user_args, **user_options)

        self._execution_counter = 0
        self._ssh = SSHLibrary()

        self.parameters = parameters
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []

        assert self._host_id, "Host ID cannot be empty"
        self._persistent = is_truthy(user_options.get('persistent', 'false'))
        self._set_worker()

    def _set_worker(self):
        if self.persistent:
            target = self._persistent_worker
        else:
            target = self._interrupt_worker
        self._thread = Thread(name=self.type, target=target, daemon=True)

    @property
    def host_alias(self):
        return self.parameters.alias

    @property
    def type(self):
        return f"{self.__class__.__name__}"

    def __str__(self):
        return "PlugIn {}: {} [Interval: {}; Persistent: {}; Sudo: {}; Password: {}]".format(
            self.type, self.host_alias, self._interval, self.persistent, self.sudo_expected,
            self.sudo_password_expected)

    def start(self):
        self._thread.start()

    def stop(self, timeout=5):
        self._internal_event.set()
        self._thread.join(timeout)

    @property
    def is_alive(self):
        return self._thread.is_alive()

    @property
    def sudo_expected(self):
        return self._sudo_expected

    @property
    def sudo_password_expected(self):
        return self._sudo_password_expected

    @property
    def interval(self):
        return self._interval

    @property
    def persistent(self):
        return self._persistent

    def __enter__(self):
        host = self.parameters.host
        port = self.parameters.port
        username = self.parameters.username
        password = self.parameters.password
        certificate = self.parameters.certificate

        if len(self._session_errors) == self._fault_tolerance:
            raise PlugInError(
                f"Stop plugin '{self.host_alias}' errors count arrived to limit ({self._fault_tolerance})")
        if len(self._session_errors) == 0:
            Logger().info(f"Connection establishing")
        else:
            Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

        self._ssh.open_connection(host, self.host_alias, port)

        start_ts = datetime.now()
        while True:
            try:
                if certificate:
                    self._ssh.login_with_public_key(username, certificate, password)
                else:
                    self._ssh.login(username, password)
            except Exception as err:
                Logger().warning(f"Connection fail; Reason: {err}")
            else:
                self._is_logged_in = True
                break
            finally:
                duration = (datetime.now() - start_ts).total_seconds()
                if duration >= self.parameters.timeout:
                    raise TimeoutError(
                        f"Cannot connect to host {self.parameters.host} during {self.parameters.timeout}s")
        Logger().info(f"SSHLibraryCommand '{self.host_alias} {self.type}' iteration started")
        return self._ssh

    def _close_ssh_library_connection_from_thread(self):
        try:
            self._ssh.close_connection()
        except Exception as e:
            if 'Logging background messages is only allowed from the main thread' in str(e):
                Logger().warning(f"Ignore SSHLibrary error: '{e}'")
                return True
            raise

    def __exit__(self, type_, value, tb):
        if value:
            self._session_errors.append(value)
            Logger().error("{name} {alias}; Error raised: {error} ({real} from {allowed})".format(
                name=self.host_alias,
                alias=self.parameters.alias,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
                error=value
            ))
        else:
            self._session_errors.clear()

        if self._is_logged_in:
            self._ssh.switch_connection(self.host_alias)
            self._close_ssh_library_connection_from_thread()
            self._is_logged_in = False
        Logger().info(f"SSHLibraryCommand '{self.host_alias} {self.parameters.alias}' iteration ended")

    @property
    def is_continue_expected(self):
        if self.parameters.event.isSet():
            Logger().info(f"Stop requested by external source")
            return False
        if self._internal_event.isSet():
            Logger().info(f"Stop requested internally")
            return False
        return True

    def _run_command(self, ssh_client: SSHLibrary, flow: Enum):
        total_output = ''
        try:
            ssh_client.switch_connection(self.host_alias)
            flow_values = getattr(self, flow.value)
            if len(flow_values) == 0:
                raise EmptyCommandSet()
            for i, cmd in enumerate(flow_values):
                run_status = cmd(ssh_client, **self.parameters)
                total_output += ('\n' if len(total_output) > 0 else '') + "{} [Result: {}]".format(cmd, run_status)
                sleep(0.05)
        except EmptyCommandSet:
            Logger().warning(f"Command set '{flow.name}' ignored")
        except Exception as e:
            f, li = get_error_info()
            err = type(e)(f"{e}; File: {f}:{li}")
            Logger().critical(f"Unexpected error occurred: {err}")
            raise err
        else:
            Logger().info(f"{flow.name}: execution completed\n{total_output}")

    def _persistent_worker(self):
        Logger().info(f"Start persistent session for '{self.host_alias}'")
        while self.is_continue_expected:
            try:
                with self as ssh:
                    self._run_command(ssh, self.flow_type.Setup)
                    while self.is_continue_expected:
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
                    self._run_command(ssh, self.flow_type.Teardown)
            except TimeoutError as e:
                self._internal_event.set()
                Logger().critical(f"{e}")
            except Exception as e:
                Logger().warning(f"Connection error; Reason: {e}")
                sleep(2)
        Logger().info(f"Persistent session for '{self}' ended")

    def _interrupt_worker(self):
        try:
            Logger().info(f"Start interrupt-session for '{self.host_alias}'")
            with self as ssh:
                self._run_command(ssh, self.flow_type.Setup)
            while self.is_continue_expected:
                with self as ssh:
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
            with self as ssh:
                self._run_command(ssh, self.flow_type.Teardown)
            Logger().info(f"End interrupt-session for '{self}'")
        except Exception as e:
            f, li = get_error_info()
            Logger().error(msg=f"{e}; File: {f}:{li}")
            raise RunnerError(f"{e}; File: {f}:{li}")
