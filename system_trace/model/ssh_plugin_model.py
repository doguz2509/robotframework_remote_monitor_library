from abc import ABCMeta
from datetime import datetime, timedelta
from enum import Enum
from threading import Thread, Event
from time import sleep
from typing import Callable, Tuple, List, AnyStr, Iterable

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException, Channel
from robot.api import logger
from robot.utils import DotDict

from system_trace.model import schema_model as model
from system_trace.model.errors import PlugInError
from system_trace.utils import Logger, get_error_info


class plugin_integration_abstract(object):
    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{id(self)}")

    @staticmethod
    def affiliated_tables() -> Tuple[model.Table]:
        return ()

    @staticmethod
    def affiliated_charts() -> Tuple[AnyStr]:
        return ()


class Command:
    def __init__(self, command, **kwargs):
        self._command = command
        self.sudo = kwargs.get('sudo', None)
        self.sudo_password = kwargs.get('sudo_password', None)
        self.interactive = kwargs.get('interactive', None)
        self.repeat = kwargs.get('repeat', 1)
        self.variable_cb = kwargs.get('variable_cb', None)

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
            Command = 'commands'
            Teardown = 'teardown'
        return FlowCommands

    @property
    def setup(self) -> CommandsType:
        return ()

    @property
    def commands(self) -> CommandsType:
        return ()

    @property
    def teardown(self) -> CommandsType:
        return ()

    @staticmethod
    def _read_channel_output(channel, buffer_size=256, interval: float = 0.05):
        buff = ''
        sleep(interval)
        while channel.recv_ready():
            buff += channel.recv(buffer_size).decode('utf-8')
            sleep(interval)
        return buff

    @staticmethod
    def _read_cmd_output(stream, buffer=1024):
        data_buffer = ''
        while stream.channel.exit_status_ready():
            if stream.channel.recv_ready():
                solo_line = stream.channel.recv(buffer)  # Retrieve the first 1024 bytes
                data_buffer += solo_line
        return data_buffer

    def _run_command(self, ssh_client: SSHClient, flow: Enum, parameters: DotDict):
        total_output = ''
        try:
            assert len(flow.value) > 0
            flow_values = getattr(self, flow.value)
            for cmd in flow_values:
                if cmd.interactive:
                    self._stored_shell[cmd.interactive] = \
                        self._stored_shell.get(cmd.interactive, ssh_client.invoke_shell())
                    for i in range(0, cmd.repeat):
                        self._stored_shell[cmd.interactive].send(cmd.command + '\n')
                        sleep(0.05)
                    output = self._read_channel_output(self._stored_shell[cmd.interactive])
                else:
                    in_, out, err = None, None, None
                    for i in range(0, cmd.repeat):
                        in_, out, err = ssh_client.exec_command(cmd.command)
                    # output = err.read().decode('UTF-8')
                    output = self._read_cmd_output(err)
                    output += '\n' if output != '' else ''
                    # output += out.read().decode('UTF-8')
                    output += self._read_cmd_output(out)
                    in_.flush()
                if cmd.variable_cb:
                    cmd.variable_cb(output)
                total_output += "Command: {}\nOutput:\n{}".format(cmd.command, output)
                sleep(0.05)
            Logger().info("{} execution completed:\n\t{}".format(flow, '\n\t'.join([f"{f}" for f in flow.value])))
        except AssertionError:
            Logger().debug(f"{flow.name} ignored")
        except Exception as e:
            f, l = get_error_info()
            raise type(e)(f"{e}; File: {f}:{l}")
        return total_output

    @staticmethod
    def parse(data_handler: Callable, affiliated_tables: Tuple[model.Table], command_output) -> bool:
        raise NotImplementedError()


class plugin_execution_abstract(plugin_integration_abstract, plugin_flow_abstract, Thread, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler):
        self._execution_counter = 0
        self._ssh: SSHClient = None
        plugin_integration_abstract.__init__(self)
        plugin_flow_abstract.__init__(self)
        self.parameters = parameters
        self._data_handler: Callable = data_handler
        self._interval = self.parameters.interval
        self._internal_event = Event()
        self._fault_tolerance = self.parameters.fault_tolerance
        self._session_errors = []

        Thread.__init__(self, name=self.name, target=self._worker, daemon=True)

    def stop(self, timeout=5):
        self._internal_event.set()
        self.join(timeout)

    @property
    def name(self):
        return f"{self.__class__.__name__}: {self.parameters.alias}"

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

            self._ssh = SSHClient()
            self._ssh.load_system_host_keys()
            if certificate:
                self._ssh.connect(host, port, username, password, key_filename=certificate)
            else:
                self._ssh.set_missing_host_key_policy(AutoAddPolicy())
                self._ssh.connect(host, port, username, password)
        except AuthenticationException:
            try:
                transport = self._ssh.get_transport()
                try:
                    transport.auth_none(username)
                except AuthenticationException:
                    pass
                transport.auth_publickey(username, None)
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
        if self._ssh:
            self._ssh.close()
            self._is_logged_in = False
        Logger().info(f"Command '{self.name} {self.parameters.alias}' iteration ended")

    @property
    def is_continue_expected(self):
        if all([not self.parameters.event.isSet(), not self._internal_event.isSet()]):
            Logger().debug(f'{self.name} - Continue')
            return True
        Logger().debug(f'{self.name} - Stop invoke')
        return False

    def __str__(self):
        return "PlugIn {}: {} [Interval: {}]".format(self.name, self.parameters.alias, self._interval)

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

    def _worker(self):
        Logger().info(f"Start interactive session for '{self.name}'")
        while self.is_continue_expected:
            with self as ssh:
                self._run_command(ssh, self.flow_type.Setup, self.parameters)
                while self.is_continue_expected:
                    start_ts = datetime.now()
                    next_ts = start_ts + timedelta(seconds=self.parameters.interval)
                    data = self._run_command(ssh, self.flow_type.Command, self.parameters)
                    self._evaluate_duration(start_ts, next_ts, self.name)
                    Logger().info("{} - {} chars received".format(self.name, len(data)))
                    self.parse(self._data_handler, self.affiliated_tables(), data)
                    self._execution_counter += 1
                    while datetime.now() < next_ts:
                        if not self.is_continue_expected:
                            break
                        sleep(0.5)
                self._run_command(ssh, self.flow_type.Teardown, self.parameters)
        Logger().info(f"End interactive session for '{self}'")
