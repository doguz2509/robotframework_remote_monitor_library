from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from threading import Thread, Event
from time import sleep
from typing import Callable, Tuple

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException, Channel

from system_trace.model import schema_model as model
from system_trace.model.schema_model import DataUnit
from system_trace.utils import Logger

DEFAULT_RECONNECT_ALLOWED = 10


class plugin_abstract:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def __hash__(self):
        return hash(f"{self.name}_{id(self)}")


class plugin_execution_abstract(plugin_abstract, Thread):
    def __init__(self, name=None, **kwargs):
        self._execution_counter = 0
        self._ssh: SSHClient = None
        plugin_abstract.__init__(self, name or self.__class__.__name__)
        Thread.__init__(self, name=self.name, target=self._worker, daemon=True)
        self._internal_event = Event()
        self._external_event = kwargs.get('event', self._internal_event)
        self._reconnection_allowed = kwargs.get('reconnect_count', DEFAULT_RECONNECT_ALLOWED)
        self._data_handler: Callable = kwargs.get('data_handler', lambda x: f"{x}")

    @property
    def affiliated_tables(self) -> Tuple[model.Table]:
        return ()

    @property
    def logger(self):
        return self.configuration.logger

    def __enter__(self):
        host = self.configuration.host
        port = self.configuration.port
        username = self.configuration.username
        password = self.configuration.password
        certificate = self.configuration.certificate
        try:
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
        else:
            self._is_logged_in = True
        return self._ssh

    def __exit__(self, type_, value, tb):
        if value:
            Logger().error("{name}; Error raised on exit: {error}\nTraceback: {tb}".format(
                name=self.name,
                error=value, tb=tb
            ))
        if self._ssh:
            self._ssh.close()
            self._is_logged_in = False

    @property
    def reconnection_allowed(self):
        return self._reconnection_allowed

    @property
    def is_continue_expected(self):
        if all([not self._external_event.isSet(), not self._internal_event.isSet()]):
            self.logger.debug('Continue')
            return True
        self.logger.debug('Stop invoke')
        return False

    def commands(self):
        raise NotImplementedError()

    def commands_text(self, delimiter=r'\n\t'):
        return delimiter.join(self.commands)

    def run_command(self, ssh: SSHClient) -> Channel:
        shell = ssh.invoke_shell()
        for command in self.commands:
            shell.send(command + '\n')
            sleep(0.05)
        self.logger.info("Command execution started\n\t{}".format('\n\t'.join(self.commands)))
        return shell

    def _worker(self):
        raise NotImplementedError()

    def parse(self, command_output: str) -> DataUnit:
        raise NotImplementedError()


class ssh_interactive_plugin(plugin_execution_abstract, metaclass=ABCMeta):
    def _worker(self):
        reconnection_count = self.reconnection_allowed

        self.logger.info(f"Start interactive session for command '{self.commands}'")
        while self.is_continue_expected:
            if reconnection_count == 0:
                self.logger.info(f"Connection establishing")
            else:
                self.logger.warning(f"Connection restoring at {reconnection_count} time")

            with self as ssh:
                shell = self.run_command(ssh)
                while self.is_continue_expected:
                    ts = datetime.now()
                    next_ts = ts + timedelta(seconds=self.configuration.interval)
                    while datetime.now() < next_ts:
                        if not self.is_continue_expected:
                            break
                        sleep(0.5)
                    data = b''
                    while shell.recv_ready():
                        data += shell.recv(4096)
                    data = data.decode('utf-8')
                    self.logger.debug("Data received:{}\n{}".format(
                        self.commands_text(), '\n\t'.join([line for line in data.splitlines()]))
                    )
                    self._data_handler(datetime.now(), self.parse(data))
                    self._execution_counter += 1
                self.logger.info(f"Command '{self.commands_text()}' execution ending")
                shell.send(chr(3))
            if self.is_continue_expected:
                self.logger.error(f"Connection lost")
                assert reconnection_count > 0, \
                    f"Connection lost arrived to limit ({self.reconnection_allowed}); Plugin stoppped"
            reconnection_count += 1

        self.logger.info(f"End interactive session for command '{self.commands_text()}'")


class ssh_non_interactive_plugin(plugin_execution_abstract, metaclass=ABCMeta):
    def _worker(self):
        reconnection_count = self.reconnection_allowed

        self.logger.info(f"Start command sequence: {self.commands_text}")
        while self.is_continue_expected:
            if reconnection_count == 0:
                self.logger.info(f"Connection establishing")
            else:
                self.logger.warning(f"Connection restoring at {reconnection_count} time")

            with self as ssh:
                shell = self.run_command(ssh)

                ts = datetime.now()
                next_ts = ts + timedelta(seconds=self.configuration.interval)
                while datetime.now() < next_ts:
                    if not self.is_continue_expected:
                        break
                    sleep(0.5)
                data = b''
                while shell.recv_ready():
                    data += shell.recv(4096)
                data = data.decode('utf-8')
                self.logger.debug("Data received:{}\n\t{}".format(
                    self.commands_text(), '\n\t'.join([line for line in data.splitlines()])))
                self._data_handler((datetime.now(), self.parse(data)))
                self._execution_counter += 1
            self.logger.info(f"Command '{self.commands_text()}' execution ended")

        self.logger.info(f"End command sequence: '{self.commands_text()}'")
