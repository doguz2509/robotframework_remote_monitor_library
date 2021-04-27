from robot.errors import RobotError


class RunnerError(RobotError):
    def __hash__(self):
        return hash(f"{self.message}")


class PlugInError(RobotError):
    def __init__(self, msg, *inner_errors):
        errors_set = set([f"{e}" for e in inner_errors])
        super().__init__(msg, "{} [{} times]\n\t{}".format(
            self.message,
            len(inner_errors),
            '\n\t'.join([f"{e}" for e in errors_set])))


class EmptyCommandSet(Exception):
    pass
