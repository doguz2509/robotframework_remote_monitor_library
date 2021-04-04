import os
from inspect import isclass, ismodule
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

    # custom_plugins_modules = {}
    # if custom_plugins:
    #     for plugins_ in re.split(r'\s*,\s*', custom_plugins):
    #         custom_plugins_modules.update(load_classes_from_module_by_name(current_dir, plugins_,
    #                                                                        plugin_execution_abstract))
    # for buildin_module in get_class_from_module(builtin_plugins):
    #     if buildin_module not in custom_plugins_modules.keys():
    #         custom_plugins_modules.update({'atop': buildin_module})