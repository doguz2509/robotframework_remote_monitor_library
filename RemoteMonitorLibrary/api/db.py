from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Thread, RLock, Timer
from time import sleep
from typing import List, AnyStr, Mapping, Tuple, Iterable

from robot.utils import DotDict

from RemoteMonitorLibrary.model.db_schema import Field, FieldType, PrimaryKeys, ForeignKey, Table, Query
from RemoteMonitorLibrary.utils import Singleton, sql, collections, Logger, get_error_info, flat_iterator
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT
from RemoteMonitorLibrary.utils.sql_engine import insert_sql
from .plugins import SSHLibraryPlugInWrapper

DEFAULT_DB_FILE = 'RemoteMonitorLibrary.db'


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
            DataHandlerService().execute(insert_sql(self.name, self.columns), *(None, timestamp))
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


class PlugInTable(Table):
    def add_time_reference(self):
        self.add_field(Field('HOST_REF', FieldType.Int))
        self.add_field(Field('TL_REF', FieldType.Int))
        self.add_foreign_key(ForeignKey('TL_REF', 'TimeLine', 'TL_ID'))
        self.add_foreign_key(ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID'))

    def add_output_cache_reference(self):
        self.add_field(Field('OUTPUT_REF', FieldType.Int))
        self.add_foreign_key(ForeignKey('OUTPUT_REF', 'LinesCacheMap', 'OUTPUT_REF'))


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
        self._result = value
        self._result_ready = True
        if self._timer:
            self._timer.cancel()

    @property
    def result_ready(self):
        return self._result_ready

    def __del__(self):
        if self._timer is not None:
            self._timer.cancel()


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
        try:
            return self._db.execute(sql_text, *rows)
        except Exception as e:
            Logger().critical(f"DB execute error: {e}")
            raise

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
                    if isinstance(item.table, PlugInTable):
                        last_tl_id = TableSchemaService().tables.TimeLine.cache_timestamp(self, item.timestamp)
                        insert_sql_str, rows = item(TL_ID=last_tl_id)
                    else:
                        insert_sql_str, rows = item()

                    result = self.execute(insert_sql_str, rows) if rows else self.execute(insert_sql_str)
                    item.result = result
                    Logger().debug("\n\t{}\n\t{}".format(insert_sql_str,
                                                         '\n\t'.join([str(r) for r in (rows if rows else result)])))
            except Exception as e:
                f, l = get_error_info()
                Logger().error(f"Unexpected error occurred: {e}; File: {f}:{l}")
            else:
                # Logger().debug(f"Item handling completed")
                sleep(1)

        Logger().debug(f"Background task stopped invoked")


@Singleton
class CacheLines:
    DEFAULT_MAX_WORKERS = 5

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

    def get_sql(self, line):
        if self.output_ref:
            return f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                      FROM LinesCacheMap 
                                      JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                      WHERE LinesCache.Line = '{line}' AND OUTPUT_REF = {self.output_ref}"""
        else:
            return f"""SELECT OUTPUT_REF, ORDER_ID, LINE_REF
                                                  FROM LinesCacheMap 
                                                  JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                                                  WHERE LinesCache.Line = '{line}' """

    def cache_line(self, line_data):
        line_id, line = line_data
        try:
            entry = DataHandlerService().execute(self.get_sql(line))
            if len(entry) == 0:
                raise _line_not_found()
            self.output_ref, order_id, line_ref = entry[0]
        except _line_not_found:
            DataHandlerService().execute(insert_sql('LinesCache', ['LINE_ID', 'Line']), *(None, line))
            line_ref = DataHandlerService().get_last_row_id
        except Exception as e:
            f, li = get_error_info()
            raise type(e)(f"Unexpected error: {e}; File: {f}:{li}")
        return line_id, line_ref

    @staticmethod
    def _compare_lines_set(output_ref, output) -> bool:
        db_entries = {k: v for k, v in DataHandlerService().execute(
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

    def upload(self, output, max_workers=DEFAULT_MAX_WORKERS):
        with ThreadPoolExecutor(max_workers=max_workers) as e:
            lines_cache = [[i, ref]
                           for i, ref in e.map(self.cache_line, [(_id, line)
                                                                 for _id, line in enumerate(output.splitlines())])]

        if self.output_ref is None or not self._compare_lines_set(self.output_ref, output):
            output_data = DataHandlerService().execute(
                TableSchemaService().tables.LinesCacheMap.queries.last_output_id.sql)
            self.output_ref = output_data[0][0] + 1 if output_data != [(None,)] else 0
            DataHandlerService().execute(insert_sql('LinesCacheMap', ['OUTPUT_REF', 'ORDER_ID', 'LINE_REF']),
                                         [[self.output_ref] + lr for lr in lines_cache])
        return self.output_ref


__all__ = [
    'DataHandlerService',
    'TableSchemaService',
    'PlugInService',
    'DB_DATETIME_FORMAT',
    'CacheLines',
    'PlugInTable',
    'DataUnit'
]
