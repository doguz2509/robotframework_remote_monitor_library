from abc import ABCMeta
from abc import ABCMeta
from datetime import datetime
from typing import Callable, Any

import paramiko
from SSHLibrary import SSHLibrary
from SSHLibrary.pythonclient import Shell
from robot.utils import DotDict, is_truthy, timestr_to_secs

from RemoteMonitorLibrary.api.tools import GlobalErrors
from RemoteMonitorLibrary.model.errors import PlugInError
from RemoteMonitorLibrary.model.runner_model import plugin_runner_abstract, Parser, Variable, ExecutionResult
from RemoteMonitorLibrary.utils.logger_helper import logger


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
        self.variable_setter = user_options.pop('variable_setter', None)
        if self.variable_setter:
            assert isinstance(self.variable_setter, Variable), "Variable setter type error"
        self.variable_getter = user_options.pop('variable_getter', None)
        if self.variable_getter:
            assert isinstance(self.variable_getter, Variable), "Variable getter vtype error"
        self.parser: Parser = user_options.pop('parser', None)
        self._sudo_expected = is_truthy(user_options.pop('sudo', False))
        self._sudo_password_expected = is_truthy(user_options.pop('sudo_password', False))
        self._start_in_folder = user_options.pop('start_in_folder', None)
        # self._alias = user_options.pop('alias', None)
        self._ssh_options = dict(_normalize_method_arguments(method.__name__, **user_options))
        self._result_template = ExecutionResult(**self._ssh_options)
        if self.parser:
            assert isinstance(self.parser, Parser), f"Parser type error [Error type: {type(self.parser).__name__}]"
        self._method = method
        self._command = command

    @property
    def command_template(self):
        _command_res = f'cd {self._start_in_folder}; ' if self._start_in_folder else ''

        _command = self._command.format(**self.variable_getter.result) if self.variable_getter else self._command

        if self._sudo_password_expected:
            _command_res += f'echo {{password}} | sudo --stdin --prompt "" {_command}'
        elif self._sudo_expected:
            _command_res += f'sudo {_command}'
        else:
            _command_res += _command
        return _command_res

    def __str__(self):
        return f"{self._method.__name__}: " \
               f"{', '.join([f'{a}' for a in [self._command] + [f'{k}={v}' for k, v in self._ssh_options.items()]])}" \
               f"{'; Parser: '.format(self.parser) if self.parser else ''}"

    def __call__(self, ssh_client: SSHLibrary, **runtime_options) -> Any:
        # ssh_client.switch_connection(str(ssh_client))
        if self._command is not None:
            command = self.command_template.format(**runtime_options)
            logger.debug(
                f"Executing: {self._method.__name__}({command}, "
                f"{', '.join([f'{k}={v}' for k, v in self._ssh_options.items()])})")
            output = self._method(ssh_client, command, **self._ssh_options)
        else:
            logger.debug(f"Executing: {self._method.__name__}"
                         f"({', '.join([f'{k}={v}' for k, v in self._ssh_options.items()])})")
            output = self._method(ssh_client, **self._ssh_options)
        if self.parser:
            return self.parser(dict(self._result_template(output)))
        if self.variable_setter:
            self.variable_setter(output)
        return output


class SSHLibraryPlugInWrapper(plugin_runner_abstract, metaclass=ABCMeta):
    def __init__(self, parameters: DotDict, data_handler, *user_args, **user_options):
        self._sudo_expected = is_truthy(user_options.pop('sudo', False))
        self._sudo_password_expected = is_truthy(user_options.pop('sudo_password', False))
        super().__init__(parameters, data_handler, *user_args, **user_options)
        self._execution_counter = 0
        self._ssh = SSHLibrary()

    @property
    def content_object(self):
        return self._ssh

    @property
    def sudo_expected(self):
        return self._sudo_expected

    @property
    def sudo_password_expected(self):
        return self._sudo_password_expected

    def _close_ssh_library_connection_from_thread(self):
        try:
            with self._lock:
                self._ssh.close_connection()
        except RuntimeError:
            pass
        except Exception as e:
            if 'Logging background messages is only allowed from the main thread' in str(e):
                logger.warn(f"Ignore SSHLibrary error: '{e}'")
                return True
            raise

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

    def open_connection(self):
        host = self.parameters.host
        port = self.parameters.port
        username = self.parameters.username
        password = self.parameters.password
        certificate = self.parameters.certificate

        if len(self._session_errors) == 0:
            logger.info(f"Host '{self.host_alias}': Connecting")
        else:
            logger.warn(f"Host '{self.host_alias}': Restoring at {len(self._session_errors)} time")

        self._ssh.open_connection(host, repr(self), port)

        start_ts = datetime.now()
        while True:
            try:
                if certificate:
                    logger.debug(f"Host '{self.host_alias}': Login with user/certificate")
                    self._ssh.login_with_public_key(username, certificate, '')
                else:
                    logger.debug(f"Host '{self.host_alias}': Login with user/password")
                    self._ssh.login(username, password)
            except paramiko.AuthenticationException:
                raise
            except Exception as e:
                logger.warn(f"Host '{self.host_alias}': Connection failed; Reason: {e}")
            else:
                self._is_logged_in = True
                logger.info(f"Host '{self.host_alias}': Connection established")
                break
            finally:
                duration = (datetime.now() - start_ts).total_seconds()
                if duration >= self.parameters.timeout:
                    raise TimeoutError(
                        f"Cannot connect to '{self.host_alias}' during {self.parameters.timeout}s")

    def close_connection(self):
        if self._is_logged_in:
            self._ssh.switch_connection(repr(self))
            self._close_ssh_library_connection_from_thread()
            self._is_logged_in = False
            logger.info(f"Host '{self.id}::{self.host_alias}': Connection closed")
        else:
            logger.info(f"Host '{self.id}::{self.host_alias}': Connection close not required (not opened)")

