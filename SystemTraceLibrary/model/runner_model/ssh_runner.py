from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Event, Thread
from time import sleep
from typing import Callable

from SSHLibrary import SSHLibrary
from robot.utils import DotDict, is_truthy

from SystemTraceLibrary.model.errors import PlugInError, RunnerError
from SystemTraceLibrary.model.runner_model.runner_abstracts import plugin_runner_abstract
from SystemTraceLibrary.utils import Logger, get_error_info


class SSHLibraryCommandScheduler(plugin_runner_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, **kwargs):
        super().__init__()
        self._execution_counter = 0
        self._ssh = SSHLibrary()

        self.parameters = parameters
        self._data_handler: Callable = data_handler
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []
        self._host_id = kwargs.get('host_id', None)
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
    def host_id(self):
        return self._host_id

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
            Logger.error(f"{err}; File: {f}:{li}")
            raise RunnerError(f"{err}; File: {f}:{li}")
        else:
            self._is_logged_in = True
        Logger().info(f"Command '{self.thread_name} {self.parameters.alias}' iteration started")
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
        Logger().info(f"Command '{self.thread_name} {self.parameters.alias}' iteration ended")

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

    @staticmethod
    def _evaluate_duration(start_ts, expected_end_ts, alias):
        end_ts = datetime.now()
        if end_ts > expected_end_ts:
            Logger().warning(
                "{}: Execution ({}) took longer then interval ({}); Recommended interval increasing up to {}s".format(
                    alias,
                    (end_ts - start_ts).total_seconds(),
                    (expected_end_ts - start_ts).total_seconds(),
                    (end_ts - start_ts).total_seconds()
                ))

    def _run_command(self, ssh_client: SSHLibrary, flow: Enum):
        total_output = ''
        try:
            ssh_client.switch_connection(self.thread_name)
            assert len(flow.value) > 0
            flow_values = getattr(self, flow.value)
            for cmd in flow_values:
                run_status = cmd(ssh_client, **self.parameters)
                total_output += "Command (Status: {}): {}\n".format(run_status, cmd)
                sleep(0.05)
            Logger().info(f"{flow.name}: execution completed\n{total_output}")
        except AssertionError:
            Logger().debug(f"{flow.name} ignored")
        except Exception as e:
            f, li = get_error_info()
            raise type(e)(f"{e}; File: {f}:{li}")

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
                        self._evaluate_duration(start_ts, next_ts, self.thread_name)
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
                    self._evaluate_duration(start_ts, next_ts, self.thread_name)
                while datetime.now() < next_ts:
                    if not self.is_continue_expected:
                        break
                    sleep(0.5)
            with self as ssh:
                self._run_command(ssh, self.flow_type.Teardown)
            Logger().info(f"End interrupt-session for '{self}'")
        except Exception as e:
            f, li = get_error_info()
            Logger.error(msg=f"{e}; File: {f}:{li}")
            raise RunnerError(f"{e}; File: {f}:{li}")

