from threading import Event, Thread
from time import sleep
from typing import List, AnyStr, Mapping

from robot.api import logger
from robot.utils import DotDict

from SystemTraceLibrary.model.schema_model import Field, FieldType, ForeignKey, Table, Query, DataUnit
from SystemTraceLibrary.model.runner_model.ssh_runner import plugin_ssh_runner
from SystemTraceLibrary.utils import Singleton, sql, threadsafe, Logger, get_error_info, flat_iterator
from SystemTraceLibrary.utils.sql_engine import insert_sql

DEFAULT_DB_FILE = 'SystemTraceLibrary.db'
TICKER_INTERVAL = 1


class TraceHost(Table):
    def __init__(self):
        super().__init__(name=None, fields=[Field('HOST_ID', FieldType.Int, True), Field('HostName')])


class TimeLine(Table):
    def __init__(self):
        Table.__init__(self, name=None,
                       fields=[Field('TL_ID', FieldType.Int, True), Field('TimeStamp', FieldType.Text)],
                       queries=[Query('select_last', 'SELECT TL_ID FROM TimeLine WHERE TimeStamp == "{timestamp}"')]
                       )

    def refresh_ts_id(self, sql_engine, timestamp):
        last_tl_id = sql_engine.execute(self.queries.select_last.sql.format(timestamp=timestamp))
        if len(last_tl_id) == 0:
            sql_engine.execute(insert_sql(self.name, [f.name for f in self.fields]), *(None, timestamp))
            last_tl_id = sql_engine.get_last_row_id
        else:
            last_tl_id = last_tl_id[0][0]
        return last_tl_id


class Points(Table):
    def __init__(self):
        Table.__init__(self,
                       fields=(Field('HOST_REF', FieldType.Int), Field('PointName'), Field('Start'), Field('End')),
                       foreign_keys=[ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID')],
                       queries=[Query('select_state', """SELECT {} FROM Points
                       WHERE HOST_REF = {} AND PointName = '{}'""")])


@Singleton
class TableSchemaService:
    def __init__(self):
        self._tables = DotDict()
        for builtin_table in (TraceHost(), TimeLine(), Points()):
            self.register_table(builtin_table)

    @property
    def tables(self):
        return self._tables

    def register_table(self, table: Table):
        self._tables[table.name] = table


@Singleton
class PlugInService(dict, Mapping[AnyStr, plugin_ssh_runner]):
    def update(self, **plugin_modules):
        for plugin in plugin_modules.values():
            for table in plugin.affiliated_tables():
                TableSchemaService().register_table(table)
        super().update(**plugin_modules)


@Singleton
class DataHandlerService(sql.SQL_DB):
    def __init__(self, location=None, file_name=DEFAULT_DB_FILE, cumulative=False):
        sql.SQL_DB.__init__(self, location, file_name, cumulative)
        self._event: Event = None
        self._threads: List[Thread] = []
        self._queue = threadsafe.tsQueue()

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

    def start(self,  event=Event()):
        if self.is_new:
            for name, table in TableSchemaService().tables.items():
                try:
                    assert not self.table_exist(table.name), f"Table '{name}' already exists"
                    self.create_table(table.name, sql.create_table_sql(table.name, table.fields,
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
        self._event.set()
        while len(self._threads) > 0:
            th = self._threads.pop(0)
            try:
                th.join(timeout)
                Logger().debug(f"Thread '{th.name}' gracefully stopped")
            except Exception as e:
                Logger().error(f"Thread '{th.name}' gracefully stop failed; Error raised: {e}")

    def _data_handler(self):
        Logger().debug(f"{self.__class__.__name__} Started with event {id(self._event)}")
        while not self._event.isSet() or not self._queue.empty():
            try:
                data_enumerator = self._queue.get()
                for item in flat_iterator(*data_enumerator):
                    if type(item).__name__ == threadsafe.Empty.__name__:
                        raise threadsafe.Empty()
                    last_tl_id = TableSchemaService().tables.TimeLine.refresh_ts_id(self, item.timestamp)
                    insert_sql_str, rows = item(TL_ID=last_tl_id)

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



