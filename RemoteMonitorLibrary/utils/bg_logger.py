import logging
import logging.handlers
import os
from threading import currentThread

from robot.api import logger as robot_logger

from .singleton import Singleton

LINE_TEMPLATE = "RemoteMonitorLibrary [Thread: {thread:15s}] -> {msg}"


@Singleton
class Logger:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        self._formatter = logging.Formatter("%(asctime)s [%(levelname)-5.7s] %(message)s")
        handler.setFormatter(self._formatter)
        self._logger.addHandler(logging.StreamHandler())

    def set_log_destination(self, file, max_bytes=(1048576 * 5), rollup_count=20, cumulative=False):
        path, file_name = os.path.split(file)
        if not os.path.exists(path):
            os.makedirs(path)
        elif not cumulative:
            if os.path.exists(file):
                os.remove(file)

        handler = logging.handlers.RotatingFileHandler(file, maxBytes=max_bytes, backupCount=rollup_count)
        handler.setFormatter(self._formatter)
        self._logger.addHandler(handler)
        if not cumulative:
            self.debug(f"File '{file}' overwritten")

        self.info(f"Logging redirected to file {file}")

    def set_level(self, level='INFO'):
        self._logger.setLevel(level)

    def _write(self, msg, level='INFO', console=False):
        thread_name = currentThread().name
        if thread_name == 'MainThread':
            robot_logger.write(msg, level)
        if console:
            robot_logger.console(msg)
        if level == 'INFO':
            self._logger.info(LINE_TEMPLATE.format(thread=thread_name, msg=msg))
        elif level == 'WARN':
            self._logger.warning(LINE_TEMPLATE.format(thread=thread_name, msg=msg))
        elif level == 'ERROR':
            self._logger.error(LINE_TEMPLATE.format(thread=thread_name, msg=msg))
        elif level == 'DEBUG':
            self._logger.debug(LINE_TEMPLATE.format(thread=thread_name, msg=msg))
        elif level == 'CRITICAL':
            self._logger.critical(LINE_TEMPLATE.format(thread=thread_name, msg=msg))

    def info(self, msg):
        self._write(msg, 'INFO')

    def debug(self, msg):
        self._write(msg, 'DEBUG')

    def warning(self, msg):
        self._write(msg, 'WARN')

    def error(self, msg):
        self._write(msg, 'ERROR')

    def critical(self, msg):
        self._write(msg, 'CRITICAL')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._logger.error(f"{exc_type}: {exc_val}\n{exc_tb}")
