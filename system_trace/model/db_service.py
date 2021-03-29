from threading import Event, Thread
from time import sleep
from typing import Iterable, List

from system_trace.model.schema_model import DbSchema
from system_trace.utils import Logger, threadsafe
from system_trace.utils.sql_engine import SQL_DB, create_table_sql
from system_trace.utils.sys_utils import get_error_info
from system_trace.utils.threadsafe import Empty

DEFAULT_DB_FILE = 'system_trace.db'
TICKER_INTERVAL = 1


class DataHandler(SQL_DB):
    def __init__(self, location=None, file_name=DEFAULT_DB_FILE, cumulative=False):
        SQL_DB.__init__(self, location, file_name, cumulative)
        self._event: Event = None
        self._threads: List[Thread] = []
        self._queue = threadsafe.tsQueue()

    @property
    def last_time_tick(self):
        return self._last_time_tick

    @property
    def is_active(self):
        return len(self._threads) == 1

    @property
    def queue(self):
        return self._queue

    def start(self,  event=Event()):

        if self.is_new:
            for _, table in DbSchema().tables.items():
                if not self.table_exist(table.name):
                    self.create_table(table.name, create_table_sql(table.name, table.fields, table.foreign_keys))

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
        while not self._event.isSet():
            try:
                Logger().debug(f"Item get invoked")
                data_enumerator = self._queue.get()
                for item in data_enumerator:
                    # if isinstance(item, Empty):
                    if type(item).__name__ == Empty.__name__:
                        raise Empty()
                    ts, tables = item
                    Logger().debug(f"{ts}")

                    last_tl_id = self.execute(f'SELECT TL_ID FROM TimeLine WHERE TimeStamp == "{ts}"')
                    if len(last_tl_id) == 0:
                        self.execute(self.tables.TimeLine.insert_sql, None, ts)
                        last_tl_id = self.get_last_row_id
                    else:
                        last_tl_id = last_tl_id[0][0]
                    if len(tables) > 0:
                        for table in tables:
                            if isinstance(table, Iterable):
                                for t in table:
                                    t.update('TL_REF', last_tl_id)
                                    self.execute(t.insert_sql, t.rows)
                            else:
                                table.update('TL_REF', last_tl_id)
                                self.execute(table.insert_sql, table.rows)
            except Empty:
                sleep(2)
            except Exception as e:
                f, l = get_error_info()
                Logger().error(f"Unexpected error occurred: {e}; File: {f}:{l}")
            else:
                Logger().debug(f"Item get completed")
                sleep(0.5)

        Logger().debug(f"Background task stopped")

