from typing import Iterable

from SSHLibrary import SSHLibrary as RSSHLibrary
from robot.utils import is_truthy

from RemoteMonitorLibrary.api import db, model
from RemoteMonitorLibrary.api.plugins import SSHLibraryCommand, PlugInAPI, Parser, extract_method_arguments
from RemoteMonitorLibrary.utils import Logger

__doc__ = """
    == SSHLibrary PlugIn ==
    Periodical execute of SSHLibrary command sequence

    === PlugIn Arguments === 
    - command_sequence: commands to be send to remote host periodically
    - user_options: regular SSHLibrary keyword arguments (See in [http://robotframework.org/SSHLibrary/SSHLibrary.html#library-documentation-top|RF SSHLibrary help])

    Plus optional three extra arguments allowed:
    - rc: int [last command should return]
    - expected: str    [output should exist]
    - prohibited: str  [output should not exists]

    command output will be evaluated for match If provided 

    === Example ===
    | Keyword  |  Arguments  |  Comments  |  
    | `Start monitor plugin`  | SSHLibrary  /usr/bin/my_command  | rc=0 [rest kwargs] |  my_command will be evaluated for return RC=0  | 
    | `Start monitor plugin`  | SSHLibrary  /usr/bin/my_command  | prohibited=Error [rest kwargs] |  my_command will be evaluated for stderr doesn't contain word 'Error'  | 



    === Limitation ===

    - SSHLibrary Plugin doesn't support interactive commands;    

    Note: 
    be aware to provide correct keyword arguments 
    """


class sshlibrary_errors(model.TimeReferencedTable):
    def __init__(self):
        model.TimeReferencedTable.__init__(self, fields=[model.Field('Command'), model.Field('Output')])


class UserCommandParser(Parser):
    def __init__(self, **kwargs):
        super().__init__(table=db.TableSchemaService().tables.sshlibrary_errors, **kwargs)

    def __call__(self, output: dict) -> bool:
        out = output.get('stdout', None)
        err = output.get('stderr', None)

        total_output = f'{out}' if out else ''
        total_output += ('\n' if len(total_output) > 0 else '') + (f'{err}' if err else '')

        rc = output.get('rc', None)

        exp_rc = self.options.get('rc', None)
        expected = self.options.get('expected', None)
        prohibited = self.options.get('prohibited', None)

        errors = []
        if exp_rc:
            exp_rc = int(exp_rc)
            if rc != exp_rc:
                errors.append(f"Rc [{rc}] not match expected - {exp_rc}")
        if expected:
            if expected not in total_output:
                errors.append("Output not contain expected pattern [{}]".format(expected))
        if prohibited:
            if prohibited in total_output:
                errors.append("Output contain prohibited pattern [{}]".format(prohibited))
        st = True
        if len(errors) > 0:
            st = False
            msg = "\nErrors:\n\t{}\n\tRC: {}\nOutput:\n\t{}".format('\n\t'.join(errors),
                                                                    rc,
                                                                    '\n\t'.join(total_output.splitlines()))
            du = db.DataUnit(self.table, self.table.template(self.host_id, None, self.options.get('command'), msg))
            self.data_handler(du)
            Logger().error(msg)
        return st


class SSHLibrary(PlugInAPI):
    def __init__(self, parameters, data_handler, command, **user_options):
        PlugInAPI.__init__(self, parameters, data_handler, command, **user_options)
        self._command = ' '.join(self.args)
        assert self._command, "Commands not provided"
        user_options = self._normalise_arguments(**user_options)
        if user_options.get('rc', None) is not None:
            assert user_options.get('return_rc'), "For verify RC argument 'return_rc' must be provided"
        if user_options.get('expected') or user_options.get('prohibited'):
            if user_options.get('return_stdout', None) is not None and not user_options.get('return_stdout'):
                assert user_options.get('return_stderr', None), \
                    "For verify expected pattern one of arguments 'return_stdout' or 'return_stderr' must be provided"

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return sshlibrary_errors(),

    @staticmethod
    def _normalise_arguments(**kwargs):
        for k in kwargs.keys():
            v = kwargs.get(k)
            if k.startswith('return'):
                kwargs.update({k: is_truthy(v)})
        return kwargs

    @property
    def periodic_commands(self):
        return SSHLibraryCommand(RSSHLibrary.execute_command, self._command,
                                 parser=UserCommandParser(host_id=self.host_id, data_handler=self.data_handler,
                                                          name=self.name, command=self._command, **self.options),
                                 **dict(extract_method_arguments(RSSHLibrary.execute_command.__name__,
                                                                 **self.options))),
