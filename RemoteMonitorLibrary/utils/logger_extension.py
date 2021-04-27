
from robot.api import logger
from robot.output import librarylogger

BASE_THREADS = librarylogger.LOGGING_THREADS


def register_logger_thread(thread_name):
    _temp = list(librarylogger.LOGGING_THREADS)
    _temp.append(thread_name)
    librarylogger.LOGGING_THREADS = tuple(_temp)
    logger.debug(f'Register logger thread: {thread_name}')


def unregister_logger_thread(thread_name):
    _temp = [_item for _item in list(librarylogger.LOGGING_THREADS) if _item != thread_name]
    logger.debug(f'De-register logger thread: {thread_name}')
    librarylogger.LOGGING_THREADS = tuple(_temp)


def reset_logger_threads():
    librarylogger.LOGGING_THREADS = BASE_THREADS
