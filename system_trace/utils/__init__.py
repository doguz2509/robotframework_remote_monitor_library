from inspect import isclass
from os.path import join as path_join

from robot.api import logger
from robot.utils import Importer

from system_trace.utils.singleton import Singleton
from system_trace.utils.sys_utils import get_error_info
from system_trace.utils.bg_logger import Logger
from system_trace.utils.size import Size

from system_trace.utils import sql_engine as sql


def get_reader_class_from_module(path, module_name, filter_class=None):
    importer = Importer("DataReader")
    abs_path = path_join(path, module_name)
    logger.debug(f"[ DataDriver ] Reader Module: {abs_path}")
    reader = importer.import_class_or_module(abs_path)
    reader_classes = {n: t for n, t in reader.__dict__.items() if isclass(t)}
    if filter_class:
        return {nn: tt for nn, tt in reader_classes.items() if issubclass(tt, filter_class)}
    return reader_classes


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
    'get_reader_class_from_module',
    'sql',
    'get_error_info',
    'flat_iterator'
]


