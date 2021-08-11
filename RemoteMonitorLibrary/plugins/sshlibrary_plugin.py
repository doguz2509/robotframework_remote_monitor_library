import re
from typing import Iterable

from SSHLibrary import SSHLibrary as RSSHLibrary
from robot.utils import is_truthy

from RemoteMonitorLibrary.utils.logger_helper import logger

from RemoteMonitorLibrary.api import model, db
from RemoteMonitorLibrary.api.plugins import *
from RemoteMonitorLibrary.model.errors import RunnerError

__doc__ = """
    == SSHLibrary PlugIn ==
    Periodical execute of SSHLibrary command sequence

    === PlugIn Arguments === 
    - command_sequence: commands to be send to remote host periodically
    - user_options: regular SSHLibrary keyword arguments (See in [http://robotframework.org/SSHLibrary/SSHLibrary.html#library-documentation-top|RF SSHLibrary help])

    Plus optional three extra arguments allowed:
    - rc:         int; Last command should return [*]
    - expected:   str; Output should exist        [**]
    - prohibited: str; Output should not exists   [**]
    - tolerance:  int; Count of errors allowed before test will be terminated (Default: 0)
                        
                        -1 - errors will be ignored, just logged 
    
    *   Support several values separated by '|'
    **  Support several values separated by '|' or '&' for OR and AND accordingly

    === Example ===
    | Keyword  |  Arguments  |  Comments  |  
    | `Start monitor plugin`  | SSHLibrary  /usr/bin/my_command  | rc=0 [rest kwargs] |  my_command will be evaluated for return RC=0  | 
    | `Start monitor plugin`  | SSHLibrary  /usr/bin/my_command  | prohibited=Error [rest kwargs] |  my_command will be evaluated for stderr doesn't contain word 'Error'  | 



    === Limitation ===

    - SSHLibrary Plugin doesn't support interactive commands;    

    Note: 
    be aware to provide correct keyword arguments 
    """


class sshlibrary_monitor(model.PlugInTable):
    def __init__(self):
        super().__init__('sshlibrary_monitor')
        self.add_time_reference()
        self.add_field(model.Field('Command'))
        self.add_field(model.Field('Rc', model.FieldType.Int))
        self.add_field(model.Field('Status'))
        self.add_output_cache_reference()


class UserCommandParser(Parser):
    def __init__(self, **kwargs):
        super().__init__(table=db.TableSchemaService().tables.sshlibrary_monitor, **kwargs)
        self._tolerance = self.options.get('tolerance')
        self._tolerance_counter = 0

    def __call__(self, output: dict) -> bool:
        out = output.get('stdout', None)
        err = output.get('stderr', None)

        total_output = f'{out}' if out else ''
        total_output += ('\n' if len(total_output) > 0 else '') + (f'{err}' if err else '')

        rc = output.get('rc', -1)

        exp_rc = self.options.get('rc', None)
        expected = self.options.get('expected', None)
        prohibited = self.options.get('prohibited', None)

        errors = []
        if exp_rc:
            if not any([int(_rc) == rc for _rc in re.split(r'\s*\|\s*', exp_rc)]):
                errors.append(f"Rc [{rc}] not match expected - {exp_rc}")
        if expected:
            if not any([pattern in total_output for pattern in re.split(r'\s*\|\s*', expected)]) or \
                    not all([pattern in total_output for pattern in re.split(r'\s*\&\s*', expected)]):
                errors.append("Output not contain expected pattern [{}]".format(expected))
        if prohibited:
            if any([pattern in total_output for pattern in re.split(r'\s*\|\s*', prohibited)]) or \
                    not all([pattern not in total_output for pattern in re.split(r'\s*\&\s*', prohibited)]):
                errors.append("Output contain prohibited pattern [{}]".format(prohibited))

        if len(errors) > 0:
            st = 'False'
            msg = "\nErrors:\n\t{}\n\tRC: {}\nOutput:\n\t{}".format('\n\t'.join(errors),
                                                                    rc,
                                                                    '\n\t'.join(total_output.splitlines()))
            logger.error(msg)
        else:
            st = 'Pass'
            msg = 'Output:\n\t{}'.format('\n\t'.join(total_output.splitlines()))
        output_ref = db.CacheLines().upload(msg)
        du = model.data_factory(self.table, self.table.template(self.host_id, None, self.options.get('command'), rc, st,
                                                                output_ref))
        self.data_handler(du)

        if st != 'Pass':
            if self._tolerance == -1:
                pass
            elif self._tolerance_counter == self._tolerance:
                raise RunnerError(f"{self}: Error count reach tolerance ({self._tolerance})", msg)
            else:
                self._tolerance_counter += 1

        return True if st == 'Pass' else False


class SSHLibrary(SSH_PlugInAPI):

    def __init__(self, parameters, data_handler, command, **user_options):
        self._command = command
        assert self._command, "Commands not provided"
        user_options.update({'name': user_options.get('name', self._command)})
        user_options.update({'tolerance': int(user_options.get('tolerance', 0))})
        super().__init__(parameters, data_handler, **user_options)

        user_options = self.normalise_arguments(**user_options)
        if user_options.get('rc', None) is not None:
            assert user_options.get('return_rc'), "For verify RC argument 'return_rc' must be provided"
        if user_options.get('expected') or user_options.get('prohibited'):
            if user_options.get('return_stdout', None) is not None and not user_options.get('return_stdout'):
                assert user_options.get('return_stderr', None), \
                    "For verify expected pattern one of arguments 'return_stdout' or 'return_stderr' must be provided"

        self.set_commands(FlowCommands.Command,
                          SSHLibraryCommand(RSSHLibrary.execute_command, self._command,
                                            parser=UserCommandParser(host_id=self.host_id,
                                                                     data_handler=self.data_handler,
                                                                     name=self.name, command=self._command,
                                                                     **self.options),
                                            **dict(extract_method_arguments(RSSHLibrary.execute_command.__name__,
                                                                            **self.options)))
                          )

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return sshlibrary_monitor(),


if __name__ == '__main__':
    t = sshlibrary_monitor()
    print(f"{t}")
