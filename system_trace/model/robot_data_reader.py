import importlib
import inspect
import os

from robot.api import logger
from robot.utils import Importer

from system_trace.model.ssh_addon import plugin_execution_abstract

#
# def _data_reader(plugin_class) -> plugin_execution_abstract:
#     # if not self.reader_config.reader_class:
#         reader_class = self._get_data_reader_from_file_extension()
#     # else:
#     #     reader_class = self._get_data_reader_from_reader_class()
#     reader_instance = reader_class(plugin_class)
#     if not isinstance(reader_instance, plugin_execution_abstract):
#         raise ImportError(
#             f"{self.reader_config.reader_class} in no instance of AbstractDataReader!"
#         )
#     return reader_instance
#
#
# def _get_data_reader_from_reader_class(self):
#     reader_name = self.reader_config.reader_class
#     logger.debug(f"[ DataDriver ] Initializes  {reader_name}")
#     if os.path.isfile(reader_name):
#         reader_class = self._get_reader_class_from_path(reader_name)
#     else:
#         local_file = os.path.join(os.path.split(os.path.realpath(__file__))[0], reader_name)
#         relative_file = os.path.join(
#             os.path.realpath(os.path.split(self.suite_source)[0]), reader_name
#         )
#         if os.path.isfile(local_file):
#             reader_class = self._get_reader_class_from_path(local_file)
#         elif os.path.isfile(relative_file):
#             reader_class = self._get_reader_class_from_path(relative_file)
#         else:
#             try:
#                 reader_class = self._get_reader_class_from_module(reader_name)
#             except Exception as e:
#                 reader_module = importlib.import_module(
#                     f"..{reader_name}", "DataDriver.DataDriver"
#                 )
#                 reader_class = getattr(reader_module, reader_name)
#     logger.debug(f"[ DataDriver ] Reader Class: {reader_class}")
#     return reader_class
#


def _get_reader_class_from_path(path, file_name) -> plugin_execution_abstract:
    logger.debug(f"[ SystemTraceLibrary ] Loading Reader from file {file_name}")
    abs_path = os.path.join(path, file_name)
    importer = Importer("DataReader")
    logger.debug(f"[ DataDriver ] Reader path: {abs_path}")
    reader = importer.import_class_or_module_by_path(abs_path)
    if not inspect.isclass(reader):
        message = f"Importing custom DataReader class from {abs_path} failed."
        raise ImportError(message)
    return reader


def _get_reader_class_from_module(path, module_name, filter_class=None):
    importer = Importer("DataReader")
    abs_path = os.path.join(path, module_name)
    logger.debug(f"[ DataDriver ] Reader Module: {abs_path}")
    reader = importer.import_class_or_module(abs_path)
    if filter_class:
        return {n: t for n, t in reader.__dict__.items() if inspect.isclass(t) and isinstance(t(), filter_class)}
    else:
        return {n: t for n, t in reader.__dict__.items() if inspect.isclass(t)}

