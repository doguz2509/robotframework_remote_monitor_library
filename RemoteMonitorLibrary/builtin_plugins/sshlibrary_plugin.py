from SSHLibrary import SSHLibrary as RSSHLibrary
from RemoteMonitorLibrary.api import db
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


class UserCommandParser(Parser):
    def __init__(self, **kwargs):
        self.output_options = {
            'return_rc': kwargs.pop('return_rc', False),
            'return_stderr': kwargs.pop('return_stderr', False),
            'return_stdout': kwargs.pop('return_stdout', True),
        }
        super().__init__(table=db.TableSchemaService().tables.Marks, **kwargs)

    def __call__(self, output: dict) -> bool:
        out = output.get('stdout')
        err = output.get('stderr')
        rc = output.get('rc')
        exp_rc = self.options.get('rc', None)
        expected = self.options.get('expected', None)
        prohibited = self.options.get('prohibited', None)
        name = self.options.get('name', self.__class__.__name__)
        errors = []
        if exp_rc:
            if rc != exp_rc:
                errors.append(AssertionError(f"Rc [{rc}] not mutch expected - {exp_rc}"))
        if expected:
            if expected not in err + out:
                errors.append(
                    AssertionError("Output not contain expected pattern [{}]\n{}".format(expected, err + out)))
        if prohibited:
            if prohibited in err + out:
                errors.append(AssertionError("Output contain prohibited pattern [{}]\n{}".format(expected, err + out)))

        if len(errors) > 0:
            msg = "Command '{}' execution not match expected criteria [{}]\nRC: {}\nOutput:\n{}".format(
                name,
                (f'RC: {rc}; ' if exp_rc else '') + (f"Expected: {expected}; " if expected else '') +
                (f"Prohibited: {prohibited}" if prohibited else ''),
                rc, err + out)
            self.data_handler(db.DataUnit(self.table, *(self.host_id, 'Error', msg)))
            Logger().error(msg)
            return False
        return True


class SSHLibrary(PlugInAPI):

    def __init__(self, parameters, data_handler, command, **user_options):
        PlugInAPI.__init__(self, parameters, data_handler, command, **user_options)
        self._command = ' '.join(self.args)
        assert self._command, "Commands not provided"

    @property
    def periodic_commands(self):
        return SSHLibraryCommand(RSSHLibrary.execute_command, self._command,
                                 parser=UserCommandParser(host_id=self.host_id, datahandler=self.data_handler,
                                                          **self.options),
                                 **dict(extract_method_arguments(RSSHLibrary.execute_command.__name__,
                                                                 **self.options))),
