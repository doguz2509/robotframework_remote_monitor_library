from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from threading import Thread, Event
from time import sleep

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException

from system_trace.model.plugin_abstract import plugin_abstract
from system_trace.utils import Logger
from system_trace.utils.configuration import Configuration


class _ssh_execution_addon_abstract(ABC, plugin_abstract):
    def __init__(self, name, configuration: Configuration):
        self._execution_counter = 0
        self._ssh: SSHClient = None
        plugin_abstract.__init__(self, name, configuration)

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

    @abstractmethod
    @property
    def command(self):
        raise NotImplementedError()


class ssh_interactive_plugin(_ssh_execution_addon_abstract, Thread, ABC):
    def __init__(self, name, configuration: Configuration, **kwargs):
        _ssh_execution_addon_abstract.__init__(self, name, configuration)
        Thread.__init__(self, name=name, target=self._worker)
        self._internal_event = Event()
        self._external_event = kwargs.get('event', self._internal_event)

    @property
    def is_continue_expected(self):
        if all([not self._external_event.isSet(), not self._internal_event.isSet()]):
            self.logger.debug('Continue')
            return True
        self.logger.debug('Stop invoke')
        return False

    def _worker(self):
        reconnection_count = 0

        self.logger.info(f"Start interactive session for command '{self.command}'")
        while self.is_continue_expected:
            if reconnection_count == 0:
                self.logger.info(f"Connection establishing")
            else:
                self.logger.warning(f"Connection restoring at {reconnection_count} time")

            with self as ssh:
                self.logger.info(f"Connection established")
                shell = ssh.invoke_shell()
                self.logger.info(f"Command '{self.command}' execution starting")
                shell.send(self.command + '\n')
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
                    self.logger.debug("Data received:\n\t{}\n\t{}".format(self.command,
                                                                           '\n\t'.join(
                                                                               [line for line in data.splitlines()])))
                    self.queue.put((datetime.now(), self.load(data)))
                    self._execution_counter += 1
                self.logger.info(f"Command '{self.command}' execution ending")
                shell.send(chr(3))
            if self.is_continue_expected:
                self.logger.error(f"Connection lost")
            reconnection_count += 1

        self.logger.info(f"End interactive session for command '{self.command}'")


class ssh_non_interactive_plugin(_ssh_execution_addon_abstract, ABC):

    @abstractmethod
    def __call__(self):
        raise NotImplementedError()


class SSH_MODES(Enum):
    Interactive = ssh_interactive_plugin
    NonInteractive = ssh_non_interactive_plugin

