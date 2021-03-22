from abc import abstractmethod

from system_trace.utils.sql_engine import SQL_DB


class _data_handler_addon_abstract:
    def __init__(self, configuration):
        self._queue = configuration.queue

    @abstractmethod
    @property
    def table_schema(self) -> dict:
        raise NotImplementedError()

    @property
    def table_schema_sql(self) -> str:
        return ''

    @abstractmethod
    @property
    def table_name(self):
        raise NotImplementedError()

    def init_addon_table(self, db_engine: SQL_DB):
        db_engine.create_table(self.table_name, self.table_schema_sql)

    def put_data(self, db_engine: SQL_DB, data):
        pass
