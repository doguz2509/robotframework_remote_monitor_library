import logging
from threading import Event

from robot.utils import DotDict

from system_trace.utils.sys_utils import get_error_info
from system_trace.utils.threadsafe import tsQueue

DEFAULT_INTERVAL = 0.5


class Configuration(DotDict):
    mandatory_fields = {
        'host': (True, None, str),
        'username': (True, None, str),
        'password': (True, None, str),
        'port': (False, 22, int),
        'run_as_sudo': (False, False, bool),
        'certificate': (False, None, str),
        'interval': (False, DEFAULT_INTERVAL, float),
        'logger': (False, logging, None),
        'event': (False, None, Event),
        'queue': (False, None, tsQueue)
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
                    value = type_(attr_value) if default else type_()
                else:
                    value = attr_value

                DotDict.__setitem__(self, attr, value)
            except AssertionError:
                f, l = get_error_info()
                err.append(f"Field '{attr}' missing; File: {f}:{l}")

        assert len(err) == 0, "Following mandatory fields missing:\n\t{}".format('\n\t'.join(err))

    def __getitem__(self, item):
        if item not in self.keys():
            return None
        return DotDict.__getitem__(self, item)

    @property
    def get_sudo(self):
        return dict(sudo=True, sudo_password=self.password)
