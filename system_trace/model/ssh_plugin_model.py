from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from threading import Thread, Event
from time import sleep, time
from typing import Callable, Tuple, List, AnyStr, Iterable

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException, Channel
from robot.api import logger

from system_trace.model import schema_model as model
from system_trace.model.configuration import Configuration
from system_trace.model.errors import PlugInError
from system_trace.utils import Logger


class plugin_abstract:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def __hash__(self):
        return hash(f"{self.name}_{id(self)}")

    @property
    def affiliated_tables(self) -> Tuple[model.Table]:
        return ()

    @property
    def affiliated_charts(self) -> Tuple[AnyStr]:
        return ()


class plugin_execution_abstract(plugin_abstract, Thread):
    def __init__(self, configuration: Configuration, data_handler, **kwargs):
        self._execution_counter = 0
        self._ssh: SSHClient = None
        plugin_abstract.__init__(self, self.__class__.__name__)
        Thread.__init__(self, name=f"{self.name} {configuration.alias}", target=self._worker, daemon=True)
        self.configuration = configuration
        self._interval = kwargs.get('interval', self.configuration.interval)
        self._internal_event = Event()
        self._fault_tolerance = kwargs.get('fault_tolerance', self.configuration.fault_tolerance)
        self._session_errors = []
        self._data_handler: Callable = data_handler

    def stop(self, timeout=5):
        self._internal_event.set()
        self.join(timeout)

    @property
    def name(self):
        return f"{self.name}: {self.configuration.alias}"

    def __enter__(self):
        host = self.configuration.host
        port = self.configuration.port
        username = self.configuration.username
        password = self.configuration.password
        certificate = self.configuration.certificate
        try:
            if len(self._session_errors) == self._fault_tolerance:
                raise PlugInError(f"Stop plugin '{self.name}' errors count arrived to limit ({self._fault_tolerance})")
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
        Logger().info(f"Command '{self.name} {self.configuration.alias}' iteration started")
        return self._ssh

    def __exit__(self, type_, value, tb):
        if value:
            self._session_errors.append(value)
            Logger().error("{name} {alias}; Error raised: {error} [{real} from {allowed}]\nTraceback: {tb}".format(
                name=self.name,
                alias=self.configuration.alias,
                real=len(self._session_errors),
                allowed=self._fault_tolerance,
                error=value, tb=tb
            ))
        else:
            self._session_errors.clear()
        if self._ssh:
            self._ssh.close()
            self._is_logged_in = False
        Logger().info(f"Command '{self.name} {self.configuration.alias}' iteration ended")

    @property
    def is_continue_expected(self):
        if all([not self.configuration.event.isSet(), not self._internal_event.isSet()]):
            Logger().debug(f'{self.name} - Continue')
            return True
        Logger().debug(f'{self.name} - Stop invoke')
        return False

    @abstractmethod
    @property
    def commands(self) -> Iterable[AnyStr]:
        raise NotImplementedError()

    def __str__(self):
        return "PlugIn {}: {} [Interval: {}]\n\tCommands:\n\t{}".format(self.name,
                                                                        self.configuration.alias,
                                                                        self._interval,
                                                                        '\n\t'.join(self.commands))

    @staticmethod
    def parse(data_handler: Callable, affiliated_tables: Tuple[model.Table], command_output) -> bool:
        raise NotImplementedError()

    def _run_command(self, ssh: SSHClient) -> Channel:
        shell = ssh.invoke_shell()
        for command in self.commands:
            if self.configuration.run_as_sudo:
                command = f'echo {self.configuration.password}|sudo --stdin --prompt "" {command}'
            shell.send(command + '\n')
            sleep(0.05)
        Logger().info("Command execution started\n\t{}".format('\n\t'.join(self.commands)))
        return shell

    def _worker(self):
        raise NotImplementedError()

    @staticmethod
    def _read_output(shell, timeout=10, raise_on_timeout=True) -> List[AnyStr]:
        data = b''
        max_time = time() + timeout
        while shell.recv_ready():
            if time() > max_time:
                if raise_on_timeout:
                    raise TimeoutError("Buffer read keep too much time")
                else:
                    break
            data += shell.recv(4096)
        data = data.decode('utf-8')
        return data.splitlines()

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


class ssh_interactive_plugin(plugin_execution_abstract, metaclass=ABCMeta):
    def _worker(self):
        Logger().info(f"Start interactive session for '{self}'")
        while self.is_continue_expected:
            if len(self._session_errors) == 0:
                Logger().info(f"Connection establishing")
            else:
                Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

            with self as ssh:
                shell = self._run_command(ssh)
                while self.is_continue_expected:
                    start_ts = datetime.now()
                    next_ts = start_ts + timedelta(seconds=self.configuration.interval)
                    data = self._read_output(shell, self.configuration.interval, False)
                    self._evaluate_duration(start_ts, next_ts, self.name)
                    Logger().info("{} - {} lines received".format(self.name, len(data)))
                    Logger().debug("{} data received:\n\t{}".format(self.name, '\n\t'.join([line for line in data])))
                    self.parse(self._data_handler, self.affiliated_tables, data)
                    self._execution_counter += 1
                    while datetime.now() < next_ts:
                        if not self.is_continue_expected:
                            break
                        sleep(0.5)
                shell.send(chr(3))

        Logger().info(f"End interactive session for '{self}'")


class ssh_non_interactive_plugin(plugin_execution_abstract, metaclass=ABCMeta):
    def _worker(self):
        while self.is_continue_expected:
            if self.is_continue_expected:
                if len(self._session_errors) == 0:
                    Logger().info(f"Connection establishing")
                else:
                    Logger().warning(f"Connection restoring at {len(self._session_errors)} time")

            with self as ssh:
                shell = self._run_command(ssh)
                start_ts = datetime.now()
                next_ts = start_ts + timedelta(seconds=self.configuration.interval)
                data = self._read_output(shell, self.configuration.interval)
                self._evaluate_duration(start_ts, next_ts, self.name)
                Logger().info("{} - {} lines received".format(self.name, len(data)))
                Logger().debug("{} data received:\n\t{}".format(self.name, '\n\t'.join([line for line in data])))

                self.parse(self._data_handler, self.affiliated_tables, data)
                self._execution_counter += 1

                while datetime.now() < next_ts:
                    if not self.is_continue_expected:
                        break
                    sleep(0.5)

        Logger().info(f"End : {self}")
