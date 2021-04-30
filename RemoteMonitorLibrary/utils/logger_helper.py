import logging
import logging.handlers
import os
from threading import currentThread

from robot.api import logger as robot_logger
from robotbackgroundlogger import BaseLogger

from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT

DEFAULT_FORMATTER = "%(asctime)s [ %(levelname)-8s ] [%(threadName)-25s::%(module)-10s::%(funcName)-10s ] : %(message)s"

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


class RenewableRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='w', maxBytes=0, backupCount=0, encoding=None, delay=False):
        _mode = mode
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.mode = _mode

        if mode == 'w':
            if self.stream:
                self.stream.close()
            self.clean_logs()

    def clean_logs(self):
        path, file = os.path.split(self.baseFilename)
        for file in [f for f in os.listdir(path) if f.startswith(file)]:
            os.remove(os.path.join(path, file))

    def __del__(self):
        try:
            self.flush()
            if self.stream:
                self.stream.close()
        except Exception as e:
            logging.warning(f"{e}")


class CustomLogger(BaseLogger):
    LOGGING_THREADS = robot_logger.librarylogger.LOGGING_THREADS

    def __init__(self, name=None):
        self._logger = logging.getLogger(name or self.__class__.__name__)

    def write(self, msg, level='INFO', html=False) -> None:
        if currentThread().getName() in self.LOGGING_THREADS:
            robot_logger.write(msg, level, html)
        else:
            self._logger.log(level_map[level], msg, stacklevel=4, exc_info=True)

    def info(self, msg, html=False, also_console=False):
        super().info(msg, html, also_console)

    def setLevel(self, level):
        self._logger.setLevel(level)

    def set_file_handler(self, file):
        handler = RenewableRotatingFileHandler(file, maxBytes=DEFAULT_MAX_BYTES, backupCount=DEFAULT_ROLLUP_COUNT)
        self.addHandler(handler)

    def addHandler(self, handler):
        handler.setFormatter(logging.Formatter(DEFAULT_FORMATTER))
        self._logger.addHandler(handler)


logger = CustomLogger()

__all__ = ['logger']
