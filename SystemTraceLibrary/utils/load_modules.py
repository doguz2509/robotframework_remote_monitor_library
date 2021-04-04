import os
from inspect import isclass
from os.path import join as path_join
from typing import Mapping, Any

from robot.api import logger
from robot.utils import Importer


def get_class_from_module(module, filter_by_class=None, deep=1) -> Mapping[str, Any]:
    print(f"{deep}: {module}")
    result = {}
    for n, m in module.__dict__.items():
        # if ismodule(m):
        #     result.update(get_class_from_module(m, filter_by_class, deep + 1))
        if isclass(m):
            if filter_by_class:
                if issubclass(m, filter_by_class):
                    result.update({n: m})
            else:
                result.update({n: m})
    return result


def filter_class_by(classes_, filter_class):
    return {nn: tt for nn, tt in classes_.items() if issubclass(tt, filter_class)}


def load_classes_from_module_by_name(path, module_name, base_class=None):
    importer = Importer("SystemTraceLibrary")
    abs_path = path_join(path, module_name)
    logger.debug(f"[ 'SystemTraceLibrary' ] Load Module: {abs_path}")
    reader = importer.import_class_or_module(abs_path)
    return get_class_from_module(reader, base_class)


def load_modules(*modules, **options):
    base_class = options.get('base_class', None)
    base_path = options.get('base_path', os.getcwd())

    result_modules = {}
    for module_ in [m for m in modules if m is not None]:
        if isinstance(module_, str):
            result_modules.update(load_classes_from_module_by_name(base_path, module_, base_class))
        elif type(module_).__name__ == 'module':
            for name, class_ in get_class_from_module(module_, base_class).items():
                if name in result_modules.keys():
                    logger.warn(f"Module '{result_modules[name]}' overloaded with '{class_}'")
                result_modules.update({name: class_})
        elif isclass(module_):
            result_modules.update({module_.__name__: module_})
    logger.debug(f"[ 'SystemTraceLibrary' ] Read Module Classes: {result_modules}")
    return result_modules


def _plugin_walk(plugins, callback):
    for k, v in plugins.items():
        callback(k, v.__name__, '')
        for t in v.affiliated_tables():
            callback('', '', t.name)


class max_lookup:
    def __init__(self):
        self._max = 0

    def __call__(self, *words):
        for i in [str(w) for w in words]:
            if len(i) > self._max:
                self._max = len(i)

    @property
    def max(self):
        return self._max


class msg_append:
    def __init__(self, column_width, *column_names):
        self._line_template = f"|{{:{column_width}s}}|{{:{column_width}s}}|{{:{column_width}s}}|\n"
        self._table_line = '+{fill}+{fill}+{fill}+\n'.format(fill='-'.join(['' for _ in range(0, column_width + 1)]))
        self._msg = self._table_line + self._line_template.format(*column_names)

    def __call__(self, *words):
        self._msg += self._line_template.format(*words)

    def __str__(self):
        return self._msg + self._table_line


def plugins_table(plugins):
    m_lookup = max_lookup()
    _plugin_walk(plugins, m_lookup)
    column_width = m_lookup.max + 2
    msg = msg_append(column_width, 'Alias', 'Class', 'Table')
    _plugin_walk(plugins, msg)
    logger.info(f"{msg}", also_console=True)
