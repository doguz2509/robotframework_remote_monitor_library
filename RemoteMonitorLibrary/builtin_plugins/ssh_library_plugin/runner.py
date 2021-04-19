from RemoteMonitorLibrary.api import plugins, db
from RemoteMonitorLibrary.model.errors import RunnerError


class UserCommandParser(plugins.Parser):
    def __init__(self, parameters, **options):
        self._options = options
        plugins.Parser.__init__(self, parameters)

    def __call__(self, output: dict) -> bool:
        out = output.get('stdout')
        err = output.get('stderr')
        rc = output.get('rc')
        exp_rc = self._options.get('rc', None)
        expected = self._options.get('expected', None)
        prohibited = self._options.get('prohibited', None)
        name = self._options.get('name', self.__class__.__name__)
        errors = []
        if exp_rc:
            if rc != exp_rc:
                errors.append(AssertionError(f"Rc [{rc}] not mutch expected - {exp_rc}"))
        if expected:
            if expected not in err + out:
                errors.append(AssertionError("Output not contain expected pattern [{}]\n{}".format(expected, err + out)))
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


class SSHLibraryCommandWithVerification(plugins.SSHLibraryCommand):
    def __init__(self, method, command, **user_options):
        self._expected = user_options.pop('expected', None)
        self._prohibited = user_options.pop('prohibited', None)
        self._rc = int(user_options.pop('rc', None))
        plugins.SSHLibraryCommand.__init__(self, method, command, **user_options)


class SSHLibraryPlugIn(plugins.PlugInAPI):
    def __init__(self, parameters, data_handler, **user_options):
        plugins.PlugInAPI.__init__(self, parameters=parameters, data_handler=data_handler)
        self._method = user_options.pop('method', None)
        self._command = user_options.pop('command', None)
        self._user_options = user_options
        self._user_options.update({
            'return_rc': True,
            'return_stderr': True,
            'return_stdout': True,
        })
        assert self._command is not None, "Command must be provided"
        assert self._method is not None, "SSHLibrary method must be provided"

    @property
    def periodic_commands(self):
        return SSHLibraryCommandWithVerification(self._method, self._command,
                                                 parser=UserCommandParser(host_id=self.host_id,
                                                                          data_handler=self.data_handler,
                                                                          **self._user_options),
                                                 **self._user_options),
