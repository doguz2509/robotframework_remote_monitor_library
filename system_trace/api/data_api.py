from threading import Event, Thread
from time import sleep
from typing import List, AnyStr, Mapping

from robot.utils import DotDict

from system_trace.model.schema_model import Field, FieldType, ForeignKey, Table, Query
from system_trace.model.ssh_plugin_model import plugin_execution_abstract
from system_trace.utils import Singleton, sql, threadsafe, Logger, get_error_info, flat_iterator
from system_trace.utils.sql_engine import insert_sql

DEFAULT_DB_FILE = 'system_trace.db'
TICKER_INTERVAL = 1
TIME_REFERENCE_FIELD = Field('TL_REF', FieldType.Int)
FOREIGN_KEY = ForeignKey('TL_REF', 'TimeLine', 'TL_ID')


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
        Table.__init__(self, fields=(Field('PointName'), Field('Start'), Field('End')))


@Singleton
class TableSchemaService:
    def __init__(self):
        self._tables = DotDict()
        for builtin_table in (TimeLine(), Points()):
            self.register_table(builtin_table, False)

    @property
    def tables(self):
        return self._tables

    def register_table(self, table: Table, assign_to_timeline=True):
        if assign_to_timeline:
            table.fields.insert(0, TIME_REFERENCE_FIELD)
            table.foreign_keys.insert(0, FOREIGN_KEY.clone())
        self._tables[table.name] = table


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

    def start(self,  event=Event()):
        if self.is_new:
            for _, table in TableSchemaService().tables.items():
                if not self.table_exist(table.name):
                    self.create_table(table.name, sql.create_table_sql(table.name, table.fields, table.foreign_keys))

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


@Singleton
class PlugInService(dict, Mapping[AnyStr, plugin_execution_abstract]):
    pass
