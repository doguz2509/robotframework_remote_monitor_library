from robot.errors import RobotError


class RunnerError(RobotError):
    pass


class PlugInError(RobotError):
    def __init__(self, msg, *inner_errors):
        super().__init__(msg)
        self.args = inner_errors


class EmptyCommandSet(Exception):
    pass
