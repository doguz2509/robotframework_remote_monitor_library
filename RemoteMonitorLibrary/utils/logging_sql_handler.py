from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import time


__version__ = "0.1.0"

from typing import Callable

from robot.utils import DotDict

initial_sql = """CREATE TABLE IF NOT EXISTS log(TimeStamp TEXT, Source TEXT, LogLevel INT, LogLevelName TEXT,
                                                Message TEXT, Module TEXT, FuncName TEXT, LineNo INT,
                                                Exception TEXT, Process INT, Thread TEXT, ThreadName TEXT)"""

INSERT_FIELDS = ('asctime', 'name', 'levelno', 'levelname', 'msg', 'module',
                 'funcName', 'lineno', 'exc_text', 'process', 'thread', 'threadName')

                 # 'dbtime', 'pathname', 'filename',
                 # 'exc_info', 'stack_info', 'created', 'msecs',
                 # 'relativeCreated', 'thread', 'threadName', 'processName', 'message']
#
# insertion_sql = """INSERT INTO log(
#                     TimeStamp,
#                     Source,
#                     LogLevel,
#                     LogLevelName,
#                     Message,
#                     Args,
#                     Module,
#                     FuncName,
#                     LineNo,
#                     Exception,
#                     Process,
#                     Thread,
#                     ThreadName
#                )
#                VALUES (
#                     '%(dbtime)s',
#                     '%(name)s',
#                     %(levelno)d,
#                     '%(levelname)s',
#                     '%(msg)s',
#                     '%(args)s',
#                     '%(module)s',
#                     '%(funcName)s',
#                     %(lineno)d,
#                     '%(exc_text)s',
#                     %(process)d,
#                     '%(thread)s',
#                     '%(threadName)s'
#                );
#                """

insertion_sql = """INSERT INTO log(TimeStamp, Source, LogLevel, LogLevelName, Message, Module, FuncName, LineNo, 
                    Exception, Process, Thread, ThreadName)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               """
#
# insertion_sql = """INSERT INTO log(
#                     TimeStamp,
#                     Source,
#                     LogLevel,
#                     LogLevelName,
#                     Message,
#                     Args,
#                     Module,
#                     FuncName,
#                     LineNo,
#                     Exception,
#                     Process,
#                     Thread,
#                     ThreadName
#                )
#                VALUES (
#                     '%(dbtime)s',
#                     '%(name)s',
#                     %(levelno)d,
#                     '%(levelname)s',
#                     '%(msg)s',
#                     '%(args)s',
#                     '%(module)s',
#                     '%(funcName)s',
#                     %(lineno)d,
#                     '%(exc_text)s',
#                     %(process)d,
#                     '%(thread)s',
#                     '%(threadName)s'
#                );
#                """


def format_time(record):
    """
    Create a time stamp
    """
    record.dbtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))


class SQLiteHandler(logging.Handler):
    """
    Thread-safe logging handler for SQLite.
    """

    def __init__(self, db_execute_method: Callable):
        logging.Handler.__init__(self)
        self._db_execute = db_execute_method
        self._db_execute(initial_sql)

    def emit(self, record):
        self.format(record)
        # format_time(record)
        if record.exc_info:  # for exceptions
            record.exc_text = logging._defaultFormatter.formatException(record.exc_info)
        else:
            record.exc_text = ""

        log_record = tuple(record.__dict__.get(key) for key in INSERT_FIELDS)
        self._db_execute(insertion_sql, *log_record)
