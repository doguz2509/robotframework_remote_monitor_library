from threading import Event, Thread
from time import sleep
from typing import List, AnyStr, Mapping

from robot.api import logger
from robot.utils import DotDict

from .model import TimeReferencedTable
from SystemTraceLibrary.model.schema_model import Field, FieldType, ForeignKey, Table, Query, DataUnit
from SystemTraceLibrary.model.runner_model.ssh_runner import SSHLibraryCommandScheduler
from SystemTraceLibrary.utils import Singleton, sql, threadsafe, Logger, get_error_info, flat_iterator
from SystemTraceLibrary.utils.sql_engine import DB_DATETIME_FORMAT, insert_sql
from SystemTraceLibrary.utils.sql_engine import insert_sql

DEFAULT_DB_FILE = 'SystemTraceLibrary.db'
TICKER_INTERVAL = 1


class TraceHost(Table):
    def __init__(self):
        super().__init__(name='TraceHost', fields=[Field('HOST_ID', FieldType.Int, True), Field('HostName')])


class TimeLine(Table):
    def __init__(self):
        Table.__init__(self, name='TimeLine',
                       fields=[Field('TL_ID', FieldType.Int, True), Field('TimeStamp', FieldType.Text)],
                       queries=[Query('select_last', 'SELECT TL_ID FROM TimeLine WHERE TimeStamp == "{timestamp}"')]
                       )

    def cache_timestamp(self, sql_engine, timestamp):
        last_tl_id = sql_engine.execute(self.queries.select_last.sql.format(timestamp=timestamp))
        if len(last_tl_id) == 0:
            DataHandlerService().execute(insert_sql(self.name, [f.name for f in self.fields]), *(None, timestamp))
            last_tl_id = sql_engine.get_last_row_id
        else:
            last_tl_id = last_tl_id[0][0]
        return last_tl_id


class Points(Table):
    def __init__(self):
        Table.__init__(self, name='Points',
                       fields=(Field('HOST_REF', FieldType.Int), Field('PointName'), Field('Start'), Field('End')),
                       foreign_keys=[ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID')],
                       queries=[Query('select_state', """SELECT {} FROM Points
                       WHERE HOST_REF = {} AND PointName = '{}'""")])


class OutputCache(Table):
    def __init__(self):
        Table.__init__(self, name=None,
                       fields=[Field('OUTPUT_ID', FieldType.Int, True), Field('Data')])

    def cache_output(self, _data):
        data_ref = DataHandlerService().execute(f"select OUTPUT_ID from OutputCache where Data = '{_data}' ")
        if len(data_ref) == 0:
            DataHandlerService().execute(insert_sql(self.name, self.columns), *(None, _data))
            data_ref = DataHandlerService().execute(f"select OUTPUT_ID from OutputCache where Data = '{_data}' ")
        return data_ref[0][0]


@Singleton
class TableSchemaService:
    def __init__(self):
        self._tables = DotDict()
        for builtin_table in (TraceHost(), TimeLine(), Points(), OutputCache()):
            self.register_table(builtin_table)

    @property
    def tables(self):
        return self._tables

    def register_table(self, table: Table):
        self._tables[table.name] = table


@Singleton
class PlugInService(dict, Mapping[AnyStr, SSHLibraryCommandScheduler]):
    def update(self, **plugin_modules):
        for plugin in plugin_modules.values():
            for table in plugin.affiliated_tables():
                TableSchemaService().register_table(table)
        super().update(**plugin_modules)


@Singleton
class DataHandlerService(sql.SQL_DB):
    def __init__(self):
        self._threads: List[Thread] = []
        self._queue = threadsafe.tsQueue()
        self._event: Event = None
        self._db: sql.SQL_DB = None

    @property
    def is_active(self):
        return len(self._threads) == 1

    @property
    def queue(self):
        if self._event.isSet():
            Logger().warning(f"Stop invoked; new data cannot be enqueued")
            return
        return self._queue

    def add_task(self, task: DataUnit):
        self.queue.put(task)

    def init(self, location=None, file_name=DEFAULT_DB_FILE, cumulative=False):
        self._db = sql.SQL_DB(location, file_name, cumulative)

    def start(self, event=Event()):
        if self._db.is_new:
            for name, table in TableSchemaService().tables.items():
                try:
                    assert not self._db.table_exist(table.name), f"Table '{name}' already exists"
                    self._db.create_table(table.name, sql.create_table_sql(table.name, table.fields,
                                                                           table.foreign_keys))
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
        return self._db.execute(sql_text, *rows)

    def _data_handler(self):
        Logger().debug(f"{self.__class__.__name__} Started with event {id(self._event)}")
        while not self._event.isSet() or not self._queue.empty():
            try:
                data_enumerator = self._queue.get()
                for item in flat_iterator(*data_enumerator):
                    if type(item).__name__ == threadsafe.Empty.__name__:
                        raise threadsafe.Empty()
                    if isinstance(item.table, TimeReferencedTable):
                        last_tl_id = TableSchemaService().tables.TimeLine.cache_timestamp(self, item.timestamp)
                        insert_sql_str, rows = item(TL_ID=last_tl_id)
                    else:
                        insert_sql_str, rows = item()

                    result = self.execute(insert_sql_str, rows) if rows else self.execute(insert_sql_str)
                    item.result = result
                    Logger().debug("\n\t{}\n\t{}".format(insert_sql_str,
                                                         '\n\t'.join([str(r) for r in (rows if rows else result)])))
            except threadsafe.Empty:
                sleep(2)
            except Exception as e:
                f, l = get_error_info()
                Logger().error(f"Unexpected error occurred: {e}; File: {f}:{l}")
            else:
                Logger().debug(f"Item get completed")
                sleep(0.5)

        Logger().debug(f"Background task stopped invoked")


__all__ = [
    'DataHandlerService',
    'TableSchemaService',
    'PlugInService',
    'DB_DATETIME_FORMAT',
    'OutputCache'
]
