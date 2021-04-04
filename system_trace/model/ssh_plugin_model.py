from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Thread, Event
from time import sleep
from typing import Callable, Iterable

from SSHLibrary import SSHLibrary
from paramiko import SSHException
from robot.api import logger
from robot.utils import DotDict

from system_trace.model.errors import PlugInError
from system_trace.utils import Logger, get_error_info


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


class plugin_flow_abstract:
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


class plugin_execution_abstract(plugin_flow_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, **kwargs):
        self._execution_counter = 0
        self._ssh = SSHLibrary()
        # plugin_integration_abstract.__init__(self)
        plugin_flow_abstract.__init__(self)
        self.parameters = parameters
        self._data_handler: Callable = data_handler
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []
        self._host_id = kwargs.get('host_id', None)
        assert self._host_id, "Host ID cannot be empty"
        if kwargs.get('persistent', False):
            target = self._persistent_worker
        else:
            target = self._interrupt_worker
        self._thread = Thread(name=self.name, target=target, daemon=True)

    @property
    def host_id(self):
        return self._host_id

    def start(self):
        self._thread.start()

    def stop(self, timeout=5):
        self._internal_event.set()
        self._thread.join(timeout)

    @property
    def type(self):
        return f"{self.__class__.__name__}"

    @property
    def name(self):
        return self.parameters.alias

    @property
    def interval(self):
        return self._interval

    def __enter__(self):
        host = self.parameters.host
        port = self.parameters.port
        username = self.parameters.username
        password = self.parameters.password
        certificate = self.parameters.certificate
        try:
            if len(self._session_errors) == self._fault_tolerance:
                raise PlugInError(f"Stop plugin '{self.name}' errors count arrived to limit ({self._fault_tolerance})")
            if len(self._session_errors) == 0:
                Logger().info(f"Connection establishing")
            else:
                Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

            self._ssh.open_connection(host, self.name, port)
            if certificate:
                self._ssh.login_with_public_key(username, certificate, password)
            else:
                self._ssh.login(username, password)
        except Exception as err:
            raise SSHException(err)
        except PlugInError as e:
            self.stop()
            logger.error(f"{e}")
        else:
            self._is_logged_in = True
        Logger().info(f"Command '{self.name} {self.parameters.alias}' iteration started")
        return self._ssh

    def __exit__(self, type_, value, tb):
        if value:
            self._session_errors.append(value)
            Logger().error("{name} {alias}; Error raised: {error} [{real} from {allowed}]\nTraceback: {tb}".format(
                name=self.name,
                alias=self.parameters.alias,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
                error=value, tb=tb
            ))
        else:
            self._session_errors.clear()

        if self._is_logged_in:
            self._ssh.switch_connection(self.name)
            self._ssh.close_connection()
            self._is_logged_in = False
        Logger().info(f"Command '{self.name} {self.parameters.alias}' iteration ended")

    @property
    def is_continue_expected(self):
        if self.parameters.event.isSet():
            Logger().info(f"Stop requested by external source")
            return False
        if self._internal_event.isSet():
            Logger().info(f"Stop requested internally")
            return False

        Logger().debug(f'{self.name} - Continue')
        return True

    def __str__(self):
        return "PlugIn {}: {} [Interval: {}]".format(self.type, self.name, self._interval)

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
            ssh_client.switch_connection(self.name)
            assert len(flow.value) > 0
            flow_values = getattr(self, flow.value)
            for cmd in flow_values:
                if cmd.interactive:
                    output = ssh_client.write(cmd.command)
                else:
                    output = ''
                    out, err, rc = '', '', 0
                    for i in range(0, cmd.repeat):
                        out, err, rc = ssh_client.execute_command(cmd.command, return_stderr=True, return_rc=True)
                        output += (err + '\n') if len(err) > 0 else ''
                        output += (out + '\n') if len(out) > 0 else ''
                        rc = rc if rc > 0 else rc
                        if cmd.variable_cb:
                            cmd.variable_cb(output.strip())
                        if cmd.parser:
                            cmd.parser(output.strip())
                    output = "RC: {}\n{}".format(rc, output)

                total_output += "Command: {}\nOutput:\n{}".format(cmd.command, output)
                sleep(0.05)
            Logger().info(f"{flow.name}: execution completed")
        except AssertionError:
            Logger().debug(f"{flow.name} ignored")
        except Exception as e:
            f, l = get_error_info()
            raise type(e)(f"{e}; File: {f}:{l}")

    def _persistent_worker(self):
        Logger().info(f"Start persistent session for '{self.name}'")
        while self.is_continue_expected:
            with self as ssh:
                self._run_command(ssh, self.flow_type.Setup)
                while self.is_continue_expected:
                    start_ts = datetime.now()
                    next_ts = start_ts + timedelta(seconds=self.parameters.interval)
                    self._run_command(ssh, self.flow_type.Command)
                    self._evaluate_duration(start_ts, next_ts, self.name)
                    while datetime.now() < next_ts:
                        if not self.is_continue_expected:
                            break
                        sleep(0.5)
                self._run_command(ssh, self.flow_type.Teardown)
        Logger().info(f"End persistent session for '{self}'")

    def _interrupt_worker(self):
        Logger().info(f"Start interrupt-session for '{self.name}'")
        with self as ssh:
            self._run_command(ssh, self.flow_type.Setup)
        while self.is_continue_expected:
            with self as ssh:
                start_ts = datetime.now()
                next_ts = start_ts + timedelta(seconds=self.parameters.interval)
                self._run_command(ssh, self.flow_type.Command)
                self._evaluate_duration(start_ts, next_ts, self.name)
            while datetime.now() < next_ts:
                if not self.is_continue_expected:
                    break
                sleep(0.5)
        with self as ssh:
            self._run_command(ssh, self.flow_type.Teardown)
        Logger().info(f"End interrupt-session for '{self}'")

    def parse(self, command_output) -> bool:
        raise NotImplementedError()
