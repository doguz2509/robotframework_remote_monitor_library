from threading import Event

from robot.utils import DotDict

from system_trace.utils.sys_utils import get_error_info

DEFAULT_INTERVAL = 0.5
DEFAULT_FAULT_TOLERANCE = 10


class Configuration(DotDict):
    mandatory_fields = {
        'index': (True, 0, int),
        'alias': (True, None, str),
        'host': (True, None, str),
        'username': (True, None, str),
        'password': (True, None, str),
        'port': (False, 22, int),
        'run_as_sudo': (False, False, bool),
        'certificate': (False, None, str),
        'interval': (False, DEFAULT_INTERVAL, float),
        'fault_tolerance': (False, DEFAULT_FAULT_TOLERANCE, int),
        'event': (False, None, Event)
    }

    def __init__(self, **kwargs):
        err = []
        attr_list = set(list(kwargs.keys()) + list(self.mandatory_fields.keys()))
        for attr in attr_list:
            try:
                mandatory, default, type_ = self.mandatory_fields.get(attr, (False, None))
                if mandatory:
                    assert attr in kwargs.keys()
                attr_value = kwargs.get(attr, default)
                if type_:
                    default = type_(default) if default else default
                    value = type_(attr_value) if attr_value else default
                else:
                    value = attr_value

                DotDict.__setitem__(self, attr, value)
            except Exception as e:
                f, l = get_error_info()
                err.append(f"Field '{attr}' missing; File: {f}:{l} - Error: {e}")

        assert len(err) == 0, "Following mandatory fields missing:\n\t{}".format('\n\t'.join(err))

    def __getitem__(self, item):
        if item not in self.keys():
            return None
        return DotDict.__getitem__(self, item)


