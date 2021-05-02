import logging
import logging.handlers
import os
from threading import currentThread

from robot.api import logger as robot_logger
from robotbackgroundlogger import BaseLogger

from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT

DEFAULT_FORMATTER = "%(asctime)s [ %(levelname)-8s ] [%(threadName)-15s ] " \
                    "[ %(module)-20s :: %(funcName)-20s ] : %(message)s"

DEFAULT_LOG_COUNT = 10
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_MAX_BYTES = (1048576 * 5)
DEFAULT_ROLLUP_COUNT = 20

# # Adopt logging levels with robot logger
logging.addLevelName(logging.DEBUG // 2, 'TRACE')
logging.TRACE = logging.DEBUG // 2
logging.addLevelName(logging.INFO, 'HTML')


# def emit(self, record) -> None:
#     for k, v in {k: v for k, v in record.__dict__.items() if k.startswith('e_')}.items():
#         if k.startswith('e_'):
#             name = k.replace('e_', '')
#             setattr(record, name, v)
#
#     self.orig_emit(record)
#
#
# logging.StreamHandler.orig_emit = logging.StreamHandler.emit
# logging.StreamHandler.emit = emit

level_map = {'TRACE': logging.DEBUG // 2,
             'DEBUG': logging.DEBUG,
             'INFO': logging.INFO,
             'HTML': logging.INFO,
             'WARN': logging.WARNING,
             'ERROR': logging.ERROR}


def clean_files(filename):
    path, file = os.path.split(filename)
    for file in [f for f in os.listdir(path) if f.startswith(file)]:
        _path = os.path.join(path, file)
        try:
            os.remove(_path)
        except PermissionError as e:
            print(f"{e}")
            raise


class CustomLogger(BaseLogger):
    LOGGING_THREADS = robot_logger.librarylogger.LOGGING_THREADS

    def __init__(self, name=None):
        self._logger = logging.getLogger(name or self.__class__.__name__)

    def write(self, msg, level='INFO', html=False) -> None:
        if currentThread().getName() in self.LOGGING_THREADS:
            robot_logger.write(msg, level, html)
        else:
            _msg = '\n'.join([(line if i == 0 else '\t\t' + line) for i, line in enumerate(msg.splitlines())])
            self._logger.log(level_map[level], _msg, stacklevel=4)

    def info(self, msg, html=False, also_console=False):
        super().info(msg, html, also_console)

    def setLevel(self, level):
        self._logger.setLevel(level)

    def set_file_handler(self, file, purge_old=True):
        if purge_old:
            clean_files(file)

        handler = logging.handlers.RotatingFileHandler(file, mode='w', maxBytes=DEFAULT_MAX_BYTES,
                                                       backupCount=DEFAULT_ROLLUP_COUNT, encoding='utf-8')
        self.addHandler(handler)

    def addHandler(self, handler):
        handler.setFormatter(logging.Formatter(DEFAULT_FORMATTER))
        self._logger.addHandler(handler)


logger = CustomLogger('RemoteMonitorLogger')

__all__ = ['logger']
