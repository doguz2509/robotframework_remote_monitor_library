from SSHLibrary import SSHLibrary as RSSHLibrary
from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.api.plugins import SSHLibraryCommand, PlugInAPI, Parser
from RemoteMonitorLibrary.utils import Logger


class UserCommandParser(Parser):
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
            self.data_handler(db.DataUnit(db.TableSchemaService().tables.Points, *(self.host_id, 'Error', msg)))


class SSHLibrary(PlugInAPI):
    def __init__(self, parameters, data_handler, **user_options):
        PlugInAPI.__init__(self, parameters=parameters, data_handler=data_handler)
        _method = user_options.pop('method', None)
        self._command = user_options.pop('command', None)
        self._user_options = user_options
        self._user_options.update({
            'return_rc': True,
            'return_stderr': True,
            'return_stdout': True,
        })
        assert self._command is not None, "Command must be provided"
        assert _method is not None, "SSHLibrary method must be provided"
        assert hasattr(RSSHLibrary(), _method), "SSHLibrary method not exists"

        self._method = getattr(RSSHLibrary(), _method)
        Logger().info(f"Method '{self._method.__name__}' assigned")

    @property
    def periodic_commands(self):
        return SSHLibraryCommand(self._method, self._command,
                                 parser=UserCommandParser(host_id=self.host_id,
                                                          data_handler=self.data_handler,
                                                          **self._user_options),
                                 **self._user_options),
