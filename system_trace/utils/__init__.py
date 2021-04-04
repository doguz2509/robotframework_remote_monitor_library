from robot.api import logger

from system_trace.utils.singleton import Singleton
from system_trace.utils.sys_utils import get_error_info
from system_trace.utils.bg_logger import Logger
from system_trace.utils.size import Size
from system_trace.utils.load_modules import get_class_from_module, load_classes_from_module_by_name, load_modules
from system_trace.utils import sql_engine as sql


def show_plugins(plugins):
    line_template = "{:20s}: {:20s}: {}\n"
    msg = line_template.format('Alias', 'Class', 'Table')
    for k, v in plugins.items():
        msg += line_template.format(k, v.__name__, '')
        for t in v.affiliated_tables():
            msg += line_template.format('', '', t.name)
    logger.info(msg, also_console=True)


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
    'show_plugins'
]


