import hashlib
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from queue import Queue
from threading import Timer, Thread, Event, RLock
from time import sleep
from typing import Tuple, Iterable, Mapping, AnyStr, List

from robot.utils import DotDict
from RemoteMonitorLibrary.utils.logger_helper import logger

from RemoteMonitorLibrary.runner import SSHLibraryPlugInWrapper
from RemoteMonitorLibrary.utils import Singleton, collections, sql_engine, flat_iterator, get_error_info
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT, insert_sql
from .tables import *
from .tables import log

DEFAULT_DB_FILE = 'RemoteMonitorLibrary.db'


class DataUnit:
    def __init__(self, table: Table, *data, **kwargs):
        self._table = table
        self._ts = kwargs.get('datetime', None) or datetime.now().strftime(kwargs.get('format', DB_DATETIME_FORMAT))
        self._timeout = kwargs.get('timeout', None)
        self._timer: Timer = None
        self._data = list(data)
        self._result = None
        self._result_ready = False

    @property
    def table(self):
        return self._table

    @property
    def timestamp(self):
        return self._ts

    @staticmethod
    def _update_foreign_fields(table, **updates):
        return {fk.own_field: updates.get(fk.foreign_field) for fk in table.foreign_keys
                if updates.get(fk.foreign_field)}

    @staticmethod
    def _update_data(table, data, **updates):
        _update_fields = DataUnit._update_foreign_fields(table, **updates)
        if len(updates) > 0:
            for i in range(0, len(data)):
                _temp = data[i]._asdict()
                _temp.update(**_update_fields)
                data[i] = table.template(**_temp)
        return data

    def get_insert_data(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        data = self._update_data(self._table, self._data, **updates)
        return str(self), [tuple(r) for r in data]

    def __str__(self):
        return insert_sql(self._table.name, self._table.columns)

    @staticmethod
    def _raise_timeout(msg):
        def _():
            raise TimeoutError(msg)

        return _

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        if self._timeout:
            self._timer = Timer(self._timeout, self._raise_timeout(f"Timeout expired on query {self}"))
            self._timer.start()
        return self.get_insert_data(**updates)

    @property
    def result(self):
        while not self.result_ready:
            sleep(0.05)
        return self._result

    @result.setter
    def result(self, value):
        if self._timer:
            self._timer.cancel()
        self._result = value
        self._result_ready = True

    @property
    def result_ready(self):
        return self._result_ready

    def __del__(self):
        if self._timer is not None:
            self._timer.cancel()


class DataRowUnitWithOutput(DataUnit):
    def __init__(self, table, *data, **kwargs):
        super().__init__(table, *data)
        self._output = kwargs.get('output', None)
        assert self._output, "Output not provided"

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        output_ref = CacheLines().upload(self._output)
        for i in range(0, len(self._data)):
            _template = DotDict(self._data[i]._asdict())
            _template.update({'OUTPUT_REF': output_ref})
            self._data[i] = self.table.template(*list(_template.values()))
        return super().__call__(**updates)


def data_factory(table, *data, **kwargs) -> DataUnit:
    _output = kwargs.get('output', None)
    if _output:
        return DataRowUnitWithOutput(table, *data, **kwargs)
    else:
        return DataUnit(table, *data, **kwargs)


@Singleton
class TableSchemaService:
    def __init__(self):
        self._tables = DotDict()
        for builtin_table in (TraceHost(), TimeLine(), Points(), LinesCache(), LinesCacheMap()):
            self.register_table(builtin_table)

    @property
    def tables(self):
        return self._tables

    def register_table(self, table: Table):
        self._tables[table.name] = table


@Singleton
class PlugInService(dict, Mapping[AnyStr, SSHLibraryPlugInWrapper]):
    def update(self, **plugin_modules):
        _registered_plugins = ''
        for plugin in plugin_modules.values():
            _registered_plugins += f'\t{plugin}\n'
            for table in plugin.affiliated_tables():
                _registered_plugins += f'\t\t{table.name}\n'
                TableSchemaService().register_table(table)
        super().update(**plugin_modules)
        logger.info(_registered_plugins)


@Singleton
class DataHandlerService:
    def __init__(self):
        self._threads: List[Thread] = []
        self._queue = Queue()
        # self._queue = collections.tsQueue()
        self._event: Event = None
        self._db: sql_engine.SQL_DB = None

    @property
    def is_active(self):
        return len(self._threads) == 1

    @property
    def db_file(self):
        return self._db.db_file

    @property
    def queue(self):
        if self._event.isSet():
            logger.warn(f"Stop invoked; new data cannot be enqueued")
            return
        return self._queue

    def init(self, location=None, file_name=DEFAULT_DB_FILE, cumulative=False):
        self._db = sql_engine.SQL_DB(location, file_name, cumulative)

    def start(self, event=Event()):
        if self._db.is_new:
            for name, table in TableSchemaService().tables.items():
                try:
                    assert not self._db.table_exist(table.name), f"Table '{name}' already exists"
                    self._db.execute(sql_engine.create_table_sql(table.name, table.fields, table.foreign_keys))
                except AssertionError as e:
                    logger.warn(f"{e}")
                except Exception as e:
                    logger.error(f"Cannot create table '{name}' -> Error: {e}")
                    raise
        self._event = event

        dh = Thread(name='DataHandler', target=self._data_handler, daemon=True)
        dh.start()
        self._threads.append(dh)

    def stop(self, timeout=5):
        if self._event:
            self._event.set()
        while len(self._threads) > 0:
            th = self._threads.pop(0)
            try:
                th.join(timeout)
                logger.debug(f"Thread '{th.name}' gracefully stopped")
            except Exception as e:
                logger.error(f"Thread '{th.name}' gracefully stop failed; Error raised: {e}")

    def execute(self, sql_text, *rows):
        try:
            return self._db.execute(sql_text, *rows)
        except Exception as e:
            logger.error("DB execute error: {}\n{}\n{}".format(e, sql_text, '\n\t'.join([r for r in rows])))
            raise

    @property
    def get_last_row_id(self):
        return self._db.get_last_row_id

    def add_data_unit(self, item: DataUnit):
        if isinstance(item.table, PlugInTable):
            last_tl_id = cache_timestamp(item.timestamp)
            item(TL_ID=last_tl_id)
            logger.debug(f"Item updated: {item.sql_data}")
        self.queue.put(item)
        logger.debug(f"Item enqueued: '{item}' (Current queue size {self.queue.qsize()})")
        # sleep(0.01)

    def _data_handler(self):
        logger.debug(f"{self.__class__.__name__} Started with event {id(self._event)}")
        while not self._event.isSet() or not self._queue.empty():
            # for item in flat_iterator(*data_enumerator):
            # if isinstance(item, collections.Empty):
            #     continue

            if self.queue.empty():
                continue

                    logger.debug(f"Dequeue item: {item}")
                    if isinstance(item.table, PlugInTable):
                        last_tl_id = cache_timestamp(item.timestamp)
                        insert_sql_str, rows = item(TL_ID=last_tl_id)
                        logger.debug(f"Update item: {item}:\n{rows}")
                    else:
                        insert_sql_str, rows = item()
                        logger.debug(f"Read item: {item}:\n{rows}")

                    result = self.execute(insert_sql_str, rows) if rows else self.execute(insert_sql_str)
                    item.result = result
                    logger.debug("{}\n\t{}\n\t{}".format(type(item).__name__,
                                                           insert_sql_str,
                                                           '\n\t'.join([str(r) for r in rows])))
                except Exception as e:
                    f, l = get_error_info()
                    logger.error(f"Unexpected error occurred on {type(item).__name__}: {e}; File: {f}:{l}")

                else:
                    logger.debug(f"Item {type(item).__name__} successfully handled")
            sleep(1)

        logger.debug(f"Background task stopped invoked")


@Singleton
class CacheLines:
    DEFAULT_MAX_WORKERS = 4

    def __init__(self):
        self._output_ref = None
        self._lock = RLock()

    @property
    def output_ref(self):
        return self._output_ref

    @output_ref.setter
    def output_ref(self, value):
        with self._lock:
            self._output_ref = value

    def get_sql(self, tag):
        if self.output_ref:
            return f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                      FROM LinesCacheMap 
                                      JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                      WHERE LinesCache.HashTag = '{tag}' AND OUTPUT_REF = {self.output_ref}"""
        else:
            return f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                                  FROM LinesCacheMap 
                                                  JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                                  WHERE LinesCache.HashTag = '{tag}' """

    @staticmethod
    def cache_line(line_data):
        order_id, line = line_data
        output_ref = None
        is_output_required = True
        try:
            hash_tag = hashlib.md5(line.encode('utf-8')).hexdigest()
            entry = DataHandlerService().execute(f"SELECT LINE_ID FROM LinesCache WHERE HashTag == '{hash_tag}'")
            if len(entry) == 0:
                DataHandlerService().execute(insert_sql('LinesCache', ['LINE_ID', 'HashTag', 'Line']),
                                             *(None, hash_tag, line))
                line_ref = DataHandlerService().get_last_row_id
            else:
                line_ref = entry[0][0]

            if is_output_required:
                entry1 = DataHandlerService().execute(f"SELECT ORDER_ID FROM LinesCacheMap WHERE LINE_REF == {line_ref}")
                if len(entry1) != 0:
                    output_ref = entry1[0][0]
                    if output_ref != order_id:
                        is_output_required = False

        except Exception as e:
            f, li = get_error_info()
            raise type(e)(f"Unexpected error: {e}; File: {f}:{li}")
        return output_ref, order_id, line_ref

    def sequence_line_cache(self, output):
        for data_item in [(_id, line) for _id, line in enumerate(output.splitlines())]:
            yield list(self.cache_line(data_item))

    def concurrent_lines_cache(self, output, max_workers):
        with ThreadPoolExecutor(max_workers=max_workers) as e:
            for output_ref, order_id, line_ref in e.map(self.cache_line,
                                                        [(_id, line) for _id, line in enumerate(output.splitlines())]):
                yield [output_ref, order_id, line_ref]

    def upload(self, output, max_workers: int = DEFAULT_MAX_WORKERS):
        logger.debug(f"Cache invoked {'concurrently' if max_workers > 1 else 'as sequence'}")
        lines_cache = list(self.concurrent_lines_cache(output, max_workers)
                           if max_workers > 1 else self.sequence_line_cache(output))

        if any([_ref[0] is None for _ref in lines_cache]):
            output_data = DataHandlerService().execute(
                TableSchemaService().tables.LinesCacheMap.queries.last_output_id.sql)
            self.output_ref = output_data[0][0] + 1 if output_data != [(None,)] else 0
            DataHandlerService().execute(insert_sql('LinesCacheMap', ['OUTPUT_REF', 'ORDER_ID', 'LINE_REF']),
                                         [[self.output_ref] + lr[1:] for lr in lines_cache])
        return self.output_ref


def cache_timestamp(timestamp):
    table = TableSchemaService().tables.TimeLine
    last_tl_id = DataHandlerService().execute(table.queries.select_last.sql.format(timestamp=timestamp))
    if len(last_tl_id) == 0:
        DataHandlerService().execute(insert_sql(table.name, table.columns), *(None, timestamp))
        last_tl_id = DataHandlerService().get_last_row_id
    else:
        last_tl_id = last_tl_id[0][0]
    return last_tl_id


class SQLiteHandler(logging.StreamHandler):
    """
    Thread-safe logging handler for SQLite.
    """
    _table = log()

    def emit(self, record):
        DataHandlerService().execute(insert_sql(self._table.name, self._table.columns), *log.format_record(record))
