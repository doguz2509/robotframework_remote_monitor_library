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
        super().__init__(table=db.TableSchemaService().tables.Marks, **kwargs)

    def __call__(self, output: dict) -> bool:
        out = output.get('stdout', None)
        err = output.get('stderr', None)
        rc = output.get('rc', None)

        exp_rc = int(self.options.get('rc', None))
        expected = self.options.get('expected', None)
        prohibited = self.options.get('prohibited', None)

        name = self.options.get('name', self.__class__.__name__)
        errors = []
        if exp_rc:
            assert rc is not None, \
                "Expected args not match vs. Verify arguments ('rc' should accomplish with 'return_rc')"
            if rc != exp_rc:
                errors.append(AssertionError(f"Rc [{rc}] not match expected - {exp_rc}"))
        if expected:
            assert any([i is not None for i in (err, out)]), \
                "Expected args not match vs. Verify arguments ('return_stdout' & 'return_stderr' " \
                "- at least one should be true)"
            if expected not in out:
                errors.append(
                    AssertionError("Output not contain expected pattern [{}]\n{}".format(expected, out)))
        if prohibited:
            assert any([i is not None for i in (err, out)]), \
                "Expected args not match vs. Verify arguments ('return_stdout' & 'return_stderr' " \
                "- at least one should be true)"
            if prohibited in out:
                errors.append(AssertionError("Output contain prohibited pattern [{}]\n{}".format(expected, out)))

        if len(errors) > 0:
            msg = "Command '{}' execution not match expected criteria [{}]\nRC: {}\nOutput:\n{}".format(
                name,
                (f'RC: {rc}; ' if exp_rc else '') + (f"Expected: {expected}; " if expected else '') +
                (f"Prohibited: {prohibited}" if prohibited else ''),
                rc, out)
            du = db.DataUnit(self.table, self.table.template(self.host_id, None, 'Error', msg))
            Logger().error(msg)
            st = False
        else:
            msg = "Command '{}' execution match expected criteria [{}]\nRC: {}\nOutput:\n{}".format(
                name,
                (f'RC: {rc}; ' if exp_rc else '') + (f"Expected: {expected}; " if expected else '') +
                (f"Prohibited: {prohibited}" if prohibited else ''),
                rc, out)
            du = db.DataUnit(self.table, self.table.template(self.host_id, None, 'Pass', msg))
            st = True
        self.data_handler(du)
        return st


class SSHLibrary(PlugInAPI):
    def __init__(self, parameters, data_handler, command, **user_options):
        PlugInAPI.__init__(self, parameters, data_handler, command, **user_options)
        self._command = ' '.join(self.args)
        assert self._command, "Commands not provided"

    @property
    def periodic_commands(self):
        return SSHLibraryCommand(RSSHLibrary.execute_command, self._command,
                                 parser=UserCommandParser(host_id=self.host_id, data_handler=self.data_handler,
                                                          **self.options),
                                 **dict(extract_method_arguments(RSSHLibrary.execute_command.__name__,
                                                                 **self.options))),
