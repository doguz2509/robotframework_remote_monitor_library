from SystemTraceLibrary.utils.singleton import Singleton
from SystemTraceLibrary.utils.sys_utils import get_error_info
from SystemTraceLibrary.utils.bg_logger import Logger
from SystemTraceLibrary.utils.size import Size
from SystemTraceLibrary.utils.load_modules import get_class_from_module, load_classes_from_module_by_name, \
    load_modules, plugins_table
from SystemTraceLibrary.utils import sql_engine as sql


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


