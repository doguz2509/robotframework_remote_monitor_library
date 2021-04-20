from RemoteMonitorLibrary.utils.singleton import Singleton
from RemoteMonitorLibrary.utils.sys_utils import get_error_info
from RemoteMonitorLibrary.utils.bg_logger import Logger
from RemoteMonitorLibrary.utils.size import Size
from .time_utils import evaluate_duration
from RemoteMonitorLibrary.utils.load_modules import get_class_from_module, load_classes_from_module_by_name, \
    load_modules, print_plugins_table
from RemoteMonitorLibrary.utils import sql_engine as sql


def flat_iterator(*data):
    for item in data:
        if isinstance(item, (list, tuple)):
            flat_iterator(*item)
        else:
            yield item


class Counter:
    def __init__(self):
        self._counter = 0

    def __str__(self):
        return f"{self._counter}"

    def __iadd__(self, other):
        self._counter += other

    def __eq__(self, other):
        return self._counter == other

    def __ne__(self, other):
        return self._counter != other

    def __gt__(self, other):
        return self._counter > other

    def __ge__(self, other):
        return self._counter >= other

    def __lt__(self, other):
        return self._counter < other

    def __le__(self, other):
        return self._counter <= other


__all__ = [
    'Singleton',
    'Logger',
    'Size',
    'sql',
    'get_error_info',
    'flat_iterator',
    'get_class_from_module',
    'load_classes_from_module_by_name',
    'load_modules',
    'print_plugins_table',
    'Counter',
    'evaluate_duration'
]


