
from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Event, Thread
from time import sleep
from typing import Callable, Any

from SSHLibrary import SSHLibrary
from robot.utils import DotDict, is_truthy, timestr_to_secs

from RemoteMonitorLibrary.model.errors import PlugInError, RunnerError
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
                                        'forward_agent': (is_truthy, False)}
}


def _normalize_arguments(ssh_library_method_name, **kwargs):
    assert ssh_library_method_name in SSHLibraryArgsMapping.keys(), f"Method {ssh_library_method_name} not supported"
    for name, value in kwargs.items():
        assert name in SSHLibraryArgsMapping.get(ssh_library_method_name, []).keys(), \
            f"Argument '{name}' not supported for '{ssh_library_method_name}'"
        arg_type, arg_default = SSHLibraryArgsMapping.get(ssh_library_method_name).get(name)
        yield name, arg_type(value)


class SSHLibraryCommand:
    def __init__(self, method: Callable, command, **user_options):
        self.variable_cb = user_options.pop('variable_cb', None)
        self.parser: Parser = user_options.pop('parser', None)
        self._sudo_expected = user_options.pop('sudo', False)
        self._sudo_password_expected = user_options.pop('sudo_password', False)
        self._start_in_folder = user_options.pop('start_in_folder', None)
        self._ssh_options = dict(_normalize_arguments(method.__name__, **user_options))
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
        command = self.command_template.format(**runtime_options)

        try:
            output = self._method(ssh_client, command, **self._ssh_options)
            if self.parser:
                return self.parser(dict(self._result_template(output)))
            return output
        except Exception as e:
            f, li = get_error_info()
            error_type = type(e)
            raise error_type(f"{self.__class__.__name__} -> {error_type.__name__}:{e}; File: {f}:{li}")


class SSHLibraryPlugInWrapper(plugin_runner_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, **kwargs):
        super().__init__(data_handler, **kwargs)
        self._execution_counter = 0
        self._ssh = SSHLibrary()

        self.parameters = parameters
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []

        assert self._host_id, "Host ID cannot be empty"
        self._persistent = is_truthy(kwargs.get('persistent', 'false'))
        self._set_worker()

    def _set_worker(self):
        if self.persistent:
            target = self._persistent_worker
        else:
            target = self._interrupt_worker
        self._thread = Thread(name=self.thread_name, target=target, daemon=True)

    @property
    def thread_name(self):
        return self.parameters.alias

    def start(self):
        self._thread.start()

    def stop(self, timeout=5):
        self._internal_event.set()
        self._thread.join(timeout)

    @property
    def type(self):
        return f"{self.__class__.__name__}"

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
        try:
            if len(self._session_errors) == self._fault_tolerance:
                raise PlugInError(
                    f"Stop plugin '{self.thread_name}' errors count arrived to limit ({self._fault_tolerance})")
            if len(self._session_errors) == 0:
                Logger().info(f"Connection establishing")
            else:
                Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

            self._ssh.open_connection(host, self.thread_name, port)
            if certificate:
                self._ssh.login_with_public_key(username, certificate, password)
            else:
                self._ssh.login(username, password)
        except Exception as err:
            f, li = get_error_info()
            self.stop()
            Logger().error(f"{err}; File: {f}:{li}")
            raise RunnerError(f"{err}; File: {f}:{li}")
        else:
            self._is_logged_in = True
        Logger().info(f"SSHLibraryCommand '{self.thread_name} {self.parameters.alias}' iteration started")
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
            Logger().error("{name} {alias}; Error raised: {error} [{real} from {allowed}]\nTraceback: {tb}".format(
                name=self.thread_name,
                alias=self.parameters.alias,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
                error=value, tb=tb
            ))
        else:
            self._session_errors.clear()

        if self._is_logged_in:
            self._ssh.switch_connection(self.thread_name)
            self._close_ssh_library_connection_from_thread()
            self._is_logged_in = False
        Logger().info(f"SSHLibraryCommand '{self.thread_name} {self.parameters.alias}' iteration ended")

    @property
    def is_continue_expected(self):
        if self.parameters.event.isSet():
            Logger().info(f"Stop requested by external source")
            return False
        if self._internal_event.isSet():
            Logger().info(f"Stop requested internally")
            return False

        Logger().debug(f'{self.thread_name} - Continue')
        return True

    def __str__(self):
        return "PlugIn {}: {} [Interval: {}; Persistent: {}]".format(self.type, self.thread_name,
                                                                     self._interval, self.persistent)

    def _run_command(self, ssh_client: SSHLibrary, flow: Enum):
        total_output = ''
        try:
            ssh_client.switch_connection(self.thread_name)
            flow_values = getattr(self, flow.value)
            assert len(flow_values) > 0
            for cmd in flow_values:
                run_status = cmd(ssh_client, **self.parameters)
                total_output += "SSHLibraryCommand {} [Result: {}]\n".format(cmd, run_status)
                sleep(0.05)
        except AssertionError:
            Logger().warning(f"{flow.name} ignored")
        except Exception as e:
            f, li = get_error_info()
            err = type(e)(f"{e}; File: {f}:{li}")
            Logger().critical(f"Unexpected error occurred: {err}")
            raise err
        else:
            Logger().info(f"{flow.name}: execution completed\n{total_output}")

    def _persistent_worker(self):
        try:
            Logger().info(f"Start persistent session for '{self.thread_name}'")
            while self.is_continue_expected:
                with self as ssh:
                    self._run_command(ssh, self.flow_type.Setup)
                    while self.is_continue_expected:
                        start_ts = datetime.now()
                        next_ts = start_ts + timedelta(seconds=self.parameters.interval)
                        self._run_command(ssh, self.flow_type.Command)
                        evaluate_duration(start_ts, next_ts, self.thread_name)
                        while datetime.now() < next_ts:
                            if not self.is_continue_expected:
                                break
                            sleep(0.5)
                    self._run_command(ssh, self.flow_type.Teardown)
            Logger().info(f"End persistent session for '{self}'")
        except Exception as e:
            f, li = get_error_info()
            Logger().error(f"{e}; File: {f}:{li}")
            raise RunnerError(f"{e}; File: {f}:{li}")

    def _interrupt_worker(self):
        try:
            Logger().info(f"Start interrupt-session for '{self.thread_name}'")
            with self as ssh:
                self._run_command(ssh, self.flow_type.Setup)
            while self.is_continue_expected:
                with self as ssh:
                    start_ts = datetime.now()
                    next_ts = start_ts + timedelta(seconds=self.parameters.interval)
                    self._run_command(ssh, self.flow_type.Command)
                    evaluate_duration(start_ts, next_ts, self.thread_name)
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

