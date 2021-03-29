import logging
import logging.handlers
import os
from threading import currentThread

from .singleton import Singleton


@Singleton
class Logger:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        self._formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(name)s  %(message)s")
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

    def info(self, msg):
        self._logger.info(f"{currentThread().name}: {msg}")

    def debug(self, msg):
        self._logger.debug(f"{currentThread().name}: {msg}")

    def warning(self, msg):
        self._logger.warning(f"{currentThread().name}: {msg}")

    def error(self, msg):
        self._logger.error(f"{currentThread().name}: {msg}")

    def critical(self, msg):
        self._logger.critical(f"{currentThread().name}: {msg}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._logger.error(f"{exc_type}: {exc_val}\n{exc_tb}")
