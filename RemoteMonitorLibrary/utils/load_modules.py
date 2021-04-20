import os
from inspect import isclass, ismodule, signature
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
    importer = Importer("RemoteMonitorLibrary")
    abs_path = path_join(path, module_name)
    logger.debug(f"[ 'RemoteMonitorLibrary' ] Load Module: {abs_path}")
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
        elif ismodule(module_):
            for name, class_ in get_class_from_module(module_, base_class).items():
                if name in result_modules.keys():
                    logger.warn(f"Module '{result_modules[name]}' overloaded with '{class_}'")
                result_modules.update({name: class_})
        elif isclass(module_):
            result_modules.update({module_.__name__: module_})
    logger.info(f"[ 'RemoteMonitorLibrary' ] Read Module Classes: {result_modules}", also_console=True)
    return result_modules


def print_plugins_table(plugins):
    _str = ''
    _delimiter = "+------------------+---------------------------+--------------------+"
    _template1 = "| {col1:16s} | {col2:25s} | {col3:18s} |"

    for name, plugin in plugins.items():
        _str += f"{_delimiter}\n"
        _str += _template1.format(col1=name, col2=' ', col3='PlugIn') + '\n'
        _str += '\n'.join([_template1.format(col1=' ', col2=t.name, col3='Table') + '\n'
                           for t in plugin.affiliated_tables()])
        for c in plugin.affiliated_charts():
            _str += _template1.format(col1=' ', col2=c.title, col3='Chart') + '\n'
            for s in c.sections:
                _str += _template1.format(col1=' ', col2='  ' + s.replace(c.title, ''), col3='Section') + '\n'
    _str += _delimiter
    logger.info(f"{_str}", also_console=True)
