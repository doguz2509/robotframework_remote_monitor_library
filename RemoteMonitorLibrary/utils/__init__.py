from RemoteMonitorLibrary.utils.singleton import Singleton
from RemoteMonitorLibrary.utils.sys_utils import get_error_info
from RemoteMonitorLibrary.utils.bg_logger import Logger
from RemoteMonitorLibrary.utils.size import Size
from RemoteMonitorLibrary.utils.load_modules import get_class_from_module, load_classes_from_module_by_name, \
    load_modules, plugins_table
from RemoteMonitorLibrary.utils import sql_engine as sql


def flat_iterator(*data):
    for item in data:
        if isinstance(item, (list, tuple)):
            flat_iterator(*item)
        else:
            yield item


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
    'plugins_table'
]


