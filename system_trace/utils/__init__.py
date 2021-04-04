from system_trace.utils.singleton import Singleton
from system_trace.utils.sys_utils import get_error_info
from system_trace.utils.bg_logger import Logger
from system_trace.utils.size import Size
from system_trace.utils.load_modules import get_class_from_module, load_classes_from_module_by_name, load_modules, \
    plugins_table
from system_trace.utils import sql_engine as sql


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


