from robot.errors import RobotError


class RunnerError(RobotError):
    def __init__(self, name, msg, *inner_errors):
        self._name = name
        self._msg = msg
        self._inner_errors = inner_errors

    def __str__(self):
        return "Plugin '{name}' error: {msg}\n\t{errors}".format(
            name=self.name, msg=self.msg,
            errors='\n\t'.join([f"{e}" for e in self.inner_errors]))

    @property
    def name(self):
        return self._name

    @property
    def msg(self):
        return self._msg

    @property
    def inner_errors(self):
        return self._inner_errors


class PlugInError(RunnerError):
    pass


class EmptyCommandSet(Exception):
    pass
