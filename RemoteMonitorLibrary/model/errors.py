from robot.errors import RobotError


class RunnerError(RobotError):
    pass


class PlugInError(RobotError):
    pass


class EmptyCommandSet(Exception):
    pass
