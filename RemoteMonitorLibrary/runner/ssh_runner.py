from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Event, Thread, RLock
from time import sleep
from typing import Callable, Any
from contextlib import contextmanager

from SSHLibrary import SSHLibrary
from SSHLibrary.pythonclient import Shell
from robot.utils import DotDict, is_truthy, timestr_to_secs

from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model.errors import PlugInError, EmptyCommandSet, RunnerError
from RemoteMonitorLibrary.model.runner_model import plugin_runner_abstract, _ExecutionResult, Parser
from RemoteMonitorLibrary.utils import get_error_info, evaluate_duration, Logger


#
# Solution for handling OSSocket error
#
def __shell_init__(self, client, term_type, term_width, term_height):
    self._shell = client.invoke_shell(term_type, term_width, term_height)
    # add use to solve socket.error: Socket is closed
    self._shell.keep_this = client


Shell.__init__ = __shell_init__


SSHLibraryArgsMapping = {
    SSHLibrary.execute_command.__name__: {'return_stdout': (is_truthy, True),
                                          'return_stderr': (is_truthy, False),
                                          'return_rc': (is_truthy, False),
                                          'sudo': (is_truthy, False),
                                          'sudo_password': (str, None),
                                          'timeout': (timestr_to_secs, None),
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
    def __init__(self, method: Callable, command=None, **user_options):
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
        if self._command is not None:
            command = self.command_template.format(**runtime_options)
            Logger().debug(
                f"Executing: {self._method.__name__}({command}, "
                f"{', '.join([f'{k}={v}' for k, v in self._ssh_options.items()])})")
            output = self._method(ssh_client, command, **self._ssh_options)
        else:
            Logger().debug(f"Executing: {self._method.__name__}"
                           f"({', '.join([f'{k}={v}' for k, v in self._ssh_options.items()])})")
            output = self._method(ssh_client, **self._ssh_options)
        if self.parser:
            return self.parser(dict(self._result_template(output)))
        return output


class SSHLibraryPlugInWrapper(plugin_runner_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, *user_args, **user_options):
        self._sudo_expected = is_truthy(user_options.pop('sudo', False))
        self._sudo_password_expected = is_truthy(user_options.pop('sudo_password', False))
        super().__init__(data_handler, *user_args, **user_options)

        self._execution_counter = 0
        self._ssh = SSHLibrary()
        self._lock = RLock()
        self._is_logged_in = False
        self.parameters = parameters
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []
        assert self._host_id, "Host ID cannot be empty"
        self._persistent = is_truthy(user_options.get('persistent', 'yes'))
        self._thread: Thread
        self._set_worker()

    def _set_worker(self):
        if self.persistent:
            target = self._persistent_worker
        else:
            target = self._interrupt_worker
        self._thread = Thread(name=self.name, target=target, daemon=True)

    @property
    def host_alias(self):
        return self.parameters.alias

    @property
    def type(self):
        return f"{self.__class__.__name__}"

    @property
    def id(self):
        return f"{self.type}-{self.name}"

    def __str__(self):
        return "{} on {} [Interval: {}; Persistent: {}; Sudo: {}; Password: {}]".format(
            self.type, self.host_alias, self._interval, self.persistent, self.sudo_expected,
            self.sudo_password_expected)

    def start(self):
        self._thread.start()

    def stop(self, timeout=20):
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

    @staticmethod
    def normalise_arguments(prefix='return', func=is_truthy, **kwargs):
        for k in kwargs.keys():
            v = kwargs.get(k)
            if k.startswith(prefix):
                kwargs.update({k: func(v)})
        return kwargs

    def _close_ssh_library_connection_from_thread(self):
        try:
            with self._lock:
                self._ssh.close_connection()
        except RuntimeError:
            pass
        except Exception as e:
            if 'Logging background messages is only allowed from the main thread' in str(e):
                Logger().warning(f"Ignore SSHLibrary error: '{e}'")
                return True
            raise

    def _evaluate_tolerance(self):
        if len(self._session_errors) == self._fault_tolerance:
            self._internal_event.set()
            raise PlugInError(
                "Stop plugin '{}' invoked; Errors count arrived to limit ({})".format(
                    self.host_alias,
                    self._fault_tolerance,
                ), *self._session_errors)

    def login(self):
        host = self.parameters.host
        port = self.parameters.port
        username = self.parameters.username
        password = self.parameters.password
        certificate = self.parameters.certificate

        if len(self._session_errors) == 0:
            Logger().info(f"Connection establishing")
        else:
            Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

        self._ssh.open_connection(host, self.host_alias, port)

        start_ts = datetime.now()
        while True:
            try:
                if certificate:
                    self._ssh.login_with_public_key(username, certificate, '')
                else:
                    self._ssh.login(username, password)
            except Exception as err:
                Logger().warning(f"Connection to {self.host_alias} failed; Reason: {err}")
                raise
            else:
                self._is_logged_in = True
                break
            finally:
                duration = (datetime.now() - start_ts).total_seconds()
                if duration >= self.parameters.timeout:
                    raise TimeoutError(
                        f"Cannot connect to {self.host_alias} during {self.parameters.timeout}s")
        Logger().info(f"Connection established to {self.host_alias}")

    def exit(self):
        if self._is_logged_in:
            # self._ssh.switch_connection(self.host_alias)
            self._close_ssh_library_connection_from_thread()
            self._is_logged_in = False
            Logger().info(f"Connection to {self.host_alias} closed")
        else:
            Logger().info(f"Connection to {self.host_alias} not opened")

    @contextmanager
    def inside_host(self):
        try:
            with self._lock:
                self.login()
                yield self._ssh
        except Exception as e:
            Logger().critical("Error connection to {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                name=self.host_alias,
                error=e,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
            ))
            GlobalErrors().append(e)
        else:
            Logger().debug('Errors cleared')
            self._session_errors.clear()
        finally:
            self.exit()

    @property
    def is_continue_expected(self):
        # if len(GlobalErrors()) > 0:
        #     Logger().critical(f"Global error occurred; Terminating")
        #     self._internal_event.isSet()
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
            Logger().debug(f"Iteration {flow.name} started")
            for i, cmd in enumerate(flow_values):
                run_status = cmd(ssh_client, **self.parameters)
                total_output += ('\n' if len(total_output) > 0 else '') + "{} [Result: {}]".format(cmd, run_status)
                sleep(0.05)
        except EmptyCommandSet:
            Logger().warning(f"Iteration {flow.name} ignored")
        except Exception as e:
            raise RunnerError(f"Command set {flow.name} failed: {e}")
        else:
            Logger().info(f"Iteration {flow.name} completed\n{total_output}")

    def _persistent_worker(self):
        Logger().info(f"\nPlugIn '{self}' started", console=True)
        while self.is_continue_expected:
            with self.inside_host() as ssh:
                self._run_command(ssh, self.flow_type.Setup)
                while self.is_continue_expected:
                    try:
                        self._evaluate_tolerance()
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
                    except RunnerError as e:
                        self._session_errors.append(e)
                        Logger().warning(
                            "Error execute on: {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                                name=self.host_alias,
                                error=e,
                                real=len(self._session_errors),
                                allowed=self._fault_tolerance,
                            ))
                sleep(2)
                self._run_command(ssh, self.flow_type.Teardown)
        sleep(2)
        Logger().info(f"PlugIn '{self}' stopped", console=True)

    def _interrupt_worker(self):
        Logger().info(f"PlugIn '{self}' started", console=True)
        with self.inside_host() as ssh:
            self._run_command(ssh, self.flow_type.Setup)
        while self.is_continue_expected:
            with self.inside_host() as ssh:
                try:
                    self._evaluate_tolerance()
                    start_ts = datetime.now()
                    _timedelta = timedelta(seconds=self.parameters.interval) \
                        if self.parameters.interval is not None else timedelta(seconds=0)
                    next_ts = start_ts + _timedelta
                    self._run_command(ssh, self.flow_type.Command)
                    if self.parameters.interval is not None:
                        evaluate_duration(start_ts, next_ts, self.host_alias)
                except RunnerError as e:
                    self._session_errors.append(e)
                    Logger().warning(
                        "Error connection to {name}; Reason: {error} (Attempt {real} from {allowed})".format(
                            name=self.host_alias,
                            error=e,
                            real=len(self._session_errors),
                            allowed=self._fault_tolerance,
                        ))
            while datetime.now() < next_ts:
                if not self.is_continue_expected:
                    break
                sleep(0.5)
        with self.inside_host() as ssh:
            self._run_command(ssh, self.flow_type.Teardown)
        Logger().info(f"End interrupt-session for '{self}'")

