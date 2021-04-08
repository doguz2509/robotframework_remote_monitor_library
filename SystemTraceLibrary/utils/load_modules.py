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


def load_classes_from_module_from_dir(path, base_class=None):
    result = {}
    for file in [f for f in os.listdir(path) if f.endswith('.py')]:
        result.update(load_classes_from_module_by_name(path, file, base_class))
    return result


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
            if os.path.isfile(os.path.normpath(os.path.join(base_path, module_))):
                result_modules.update(load_classes_from_module_by_name(base_path, module_, base_class))
            else:
                result_modules.update(
                    load_classes_from_module_from_dir(os.path.normpath(os.path.join(base_path, module_)),
                                                      base_class))
        elif type(module_).__name__ == 'module':
            for name, class_ in get_class_from_module(module_, base_class).items():
                if name in result_modules.keys():
                    logger.warn(f"Module '{result_modules[name]}' overloaded with '{class_}'")
                result_modules.update({name: class_})
        elif isclass(module_):
            result_modules.update({module_.__name__: module_})
    logger.info(f"[ 'SystemTraceLibrary' ] Read Module Classes: {result_modules}", also_console=True)
    return result_modules


def _plugin_walk(plugins, callback):
    for k, v in plugins.items():
        callback(name=v.__name__)
        for t in v.affiliated_tables():
            callback(addon=f"{t.name:42s} [Table]")
        for t in v.affiliated_charts():
            callback(addon=f"{t.title:15s}: {', '.join(t.sections):20s} [Chart]")


class max_lookup:
    def __init__(self):
        self._plugin_max = 0
        self._addon_max = 0

    def __call__(self, **words):
        for n, v in words.items():
            if n == 'name':
                if len(v) > self._plugin_max:
                    self._plugin_max = len(v)
            elif n == 'addon':
                if len(v) > self._addon_max:
                    self._addon_max = len(v)

    @property
    def max(self):
        return dict(name=self._plugin_max, addon=self._addon_max)


class msg_append:
    def __init__(self, *column_names, **width):
        self._line_template = f"|{{name:{width.get('name')}s}}|{{addon:{width.get('addon')}s}}|\n"
        self._table_line = '+{name_width}+{addon_width}+\n'.format(
            name_width='-'.join(['' for _ in range(0, width.get('name') + 1)]),
            addon_width='-'.join(['' for _ in range(0, width.get('addon') + 1)]))
        self._msg = self._table_line + self._line_template.format(name=column_names[0], addon=column_names[1])

    def __call__(self, **words):
        if 'name' in words.keys():
            words.update({'addon': ''})
        elif 'addon' in words.keys():
            words.update({'name': ''})
        self._msg += self._line_template.format(**words)

    def __str__(self):
        return self._msg + self._table_line


def plugins_table(plugins):
    m_lookup = max_lookup()
    _plugin_walk(plugins, m_lookup)
    m_lookup(name='PlugIn Name', addon='Tables / Charts')
    columns_width = m_lookup.max
    msg = msg_append('PlugIn Name', 'Tables / Charts', **columns_width)
    _plugin_walk(plugins, msg)
    logger.info(f"{msg}", also_console=True)
