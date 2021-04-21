from threading import Event, Thread
from time import sleep
from typing import List, AnyStr, Mapping

from robot.utils import DotDict

from RemoteMonitorLibrary.model.db_schema import Field, FieldType, PrimaryKeys, ForeignKey, Table, Query, DataUnit
from RemoteMonitorLibrary.utils import Singleton, sql, collections, Logger, get_error_info, flat_iterator
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT
from RemoteMonitorLibrary.utils.sql_engine import insert_sql
from .model import TimeReferencedTable
from .plugins import SSHLibraryPlugInWrapper

DEFAULT_DB_FILE = 'RemoteMonitorLibrary.db'
TICKER_INTERVAL = 1


class TraceHost(Table):
    def __init__(self):
        super().__init__(name='TraceHost',
                         fields=[Field('HOST_ID', FieldType.Int, PrimaryKeys(True)), Field('HostName')])


class TimeLine(Table):
    def __init__(self):
        Table.__init__(self, name='TimeLine',
                       fields=[Field('TL_ID', FieldType.Int, PrimaryKeys(True)), Field('TimeStamp', FieldType.Text)],
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


class LinesCacheMap(Table):
    def __init__(self):
        super().__init__(fields=[Field('OUTPUT_REF', FieldType.Int), Field('ORDER_ID', FieldType.Int),
                                 Field('LINE_REF', FieldType.Int)],
                         foreign_keys=[ForeignKey('OUTPUT_REF', 'TimeMeasurement', 'OUTPUT_ID'),
                                       ForeignKey('LINE_REF', 'LinesCache', 'LINE_ID')],
                         queries=[Query('last_output_id', 'select max(OUTPUT_REF) from LinesCacheMap')])


class LinesCache(Table):
    def __init__(self):
        Table.__init__(self, fields=[Field('LINE_ID', FieldType.Int, PrimaryKeys(True)), Field('Line')])


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
        Logger().info(_registered_plugins)


class _line_not_found(AssertionError):
    pass


@Singleton
class DataHandlerService:
    def __init__(self):
        self._threads: List[Thread] = []
        self._queue = collections.tsQueue()
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
                    self._db.execute(sql.create_table_sql(table.name, table.fields, table.foreign_keys))
                except AssertionError as e:
                    Logger().warn(f"{e}")
                except Exception as e:
                    Logger().error(f"Cannot create table '{name}' -> Error: {e}")
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
                Logger().debug(f"Thread '{th.name}' gracefully stopped")
            except Exception as e:
                Logger().error(f"Thread '{th.name}' gracefully stop failed; Error raised: {e}")

    def execute(self, sql_text, *rows):
        return self._db.execute(sql_text, *rows)

    @property
    def get_last_row_id(self):
        return self._db.get_last_row_id

    def _data_handler(self):
        Logger().debug(f"{self.__class__.__name__} Started with event {id(self._event)}")
        while not self._event.isSet() or not self._queue.empty():
            try:
                data_enumerator = self._queue.get()
                for item in flat_iterator(*data_enumerator):
                    if isinstance(item, collections.Empty):
                        continue
                    if isinstance(item.table, TimeReferencedTable):
                        last_tl_id = TableSchemaService().tables.TimeLine.cache_timestamp(self, item.timestamp)
                        insert_sql_str, rows = item(TL_ID=last_tl_id)
                    else:
                        insert_sql_str, rows = item()

                    result = self.execute(insert_sql_str, rows) if rows else self.execute(insert_sql_str)
                    item.result = result
                    Logger().debug("\n\t{}\n\t{}".format(insert_sql_str,
                                                         '\n\t'.join([str(r) for r in (rows if rows else result)])))
            # except collections.Empty:
            #     sleep(2)
            except Exception as e:
                f, l = get_error_info()
                Logger().error(f"Unexpected error occurred: {e}; File: {f}:{l}")
            else:
                Logger().debug(f"Item handling completed")
                sleep(0.5)

        Logger().debug(f"Background task stopped invoked")

    def _cache_lines(self, output):
        output_ref = None
        lines_cache = []
        for line_id, line in enumerate(output.splitlines()):
            try:
                if output_ref:
                    entry = self.execute(
                        f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                   FROM LinesCacheMap 
                                   JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                   WHERE LinesCache.Line = '{line}' AND OUTPUT_REF = {output_ref}""")
                else:
                    entry = self.execute(
                        f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                   FROM LinesCacheMap 
                                   JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                   WHERE LinesCache.Line = '{line}' """)
                if len(entry) == 0:
                    raise _line_not_found()
                output_ref, order_id, line_ref = entry[0]
            except _line_not_found:
                DataHandlerService().execute(insert_sql('LinesCache', ['LINE_ID', 'Line']), *(None, line))
                line_ref = self.get_last_row_id

            lines_cache.append([line_id, line_ref])
        return output_ref, lines_cache

    def _compare_lines_set(self, output_ref, output) -> bool:
        db_entries = {k: v for k, v in self.execute(
            f"""SELECT ORDER_ID, Line
                FROM LinesCacheMap 
                JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                WHERE OUTPUT_REF = {output_ref}""")}
        current_entries = {ord_id: line for ord_id, line in enumerate(output.splitlines())}

        for o, line in current_entries.items():
            try:
                assert line == db_entries.get(o, None)
            except AssertionError:
                return False
        return True

    def cache_output(self, output: str):
        output_ref, line_ref = self._cache_lines(output)

        if output_ref is None or not self._compare_lines_set(output_ref, output):
            output_data = DataHandlerService().execute(
                            TableSchemaService().tables.LinesCacheMap.queries.last_output_id.sql)
            output_ref = output_data[0][0] + 1 if output_data != [(None,)] else 0
            self.execute(insert_sql('LinesCacheMap', ['OUTPUT_REF', 'ORDER_ID', 'LINE_REF']),
                         [[output_ref] + lr for lr in line_ref])

        return output_ref


__all__ = [
    'DataHandlerService',
    'TableSchemaService',
    'PlugInService',
    'DB_DATETIME_FORMAT'
]
