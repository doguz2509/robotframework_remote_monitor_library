from collections import namedtuple
from datetime import datetime
from enum import Enum
from threading import Timer
from time import sleep
from typing import List, Iterable, Tuple

from robot.utils import DotDict

from system_trace.utils import sql
from system_trace.utils.sql_engine import insert_sql, update_sql, select_sql, DB_DATETIME_FORMAT


class FieldType(Enum):
    Int = 'INTEGER'
    Text = 'TEXT'
    Real = 'REAL'


class Field:
    def __init__(self, name, type_: FieldType = None, key=False):
        """
        Table field definition
        :param name: Table name string
        :param type_: field type (INTEGER, TEXT, REAL)
        """

        self._name: str = name
        self._type: FieldType = type_ or FieldType.Text
        self._key = key

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def key(self):
        return self._key

    def __str__(self):
        return f"{self.name} {self.type.value}{' PRIMARY KEY' if self.key else ''}"


class Query:
    def __init__(self, name: str, sql: str, formatter=format):
        """
        Query assigned for Table
        :param name: query name string
        :param sql: SQL statement in python format (Mandatory variables)
        :param formatter: input arguments formatter
        """
        self._name = name
        self._sql = sql
        self._formatter = formatter

    @property
    def name(self):
        return self._name

    @property
    def sql(self):
        return self._sql


class ForeignKey:
    def __init__(self, own_field, foreign_table, foreign_field):
        """
        Foreign key definition for table
        :param own_field: Own field name
        :param foreign_table: Foreign table name
        :param foreign_field: Foreign field name
        """

        self._own_field = own_field
        self._table = foreign_table
        self._field = foreign_field

    @property
    def own_field(self):
        return self._own_field

    @property
    def foreign_table(self):
        return self._table

    @property
    def foreign_field(self):
        return self._field

    def __str__(self):
        return sql.FOREIGN_KEY_TEMPLATE.format(local_field=self.own_field,
                                               foreign_table=self.foreign_table,
                                               foreign_field=self.foreign_field)

    def clone(self):
        return type(self)(self.own_field, self.foreign_table, self.foreign_field)


class Table(object):
    def __init__(self, name=None, fields: Iterable[Field] = None, queries: Iterable[Query] = None,
                 foreign_keys: List[ForeignKey] = None):
        self._name = name or self.__class__.__name__
        self._fields: List[Field] = fields or []
        self._queries: DotDict[str, Query] = DotDict()
        self._foreign_keys: List[ForeignKey] = foreign_keys or []
        for query in queries or []:
            self._queries[query.name] = query

    @property
    def template(self):
        return namedtuple(self.name, (f.name for f in self.fields))

    @property
    def fields(self):
        return self._fields

    @property
    def columns(self):
        return [f.name for f in self.fields]

    @property
    def name(self):
        return self._name

    @property
    def queries(self):
        return self._queries

    @property
    def foreign_keys(self):
        return self._foreign_keys


class SQL_ACTIONS(Enum):
    SELECT = 'select'
    INSERT = 'insert'
    UPDATE = 'update'


class DataUnit:
    def __init__(self, table: Table, *data, **kwargs):
        self._table = table
        self._ts = datetime.now().strftime(kwargs.get('format', DB_DATETIME_FORMAT))
        # self._sql_statement = kwargs.get('sql', None)
        # if self._sql_statement:
        #     self._sql_action = SQL_ACTIONS[self._sql_statement.split(' ')[0].strip().upper()]
        # else:
        #     self._sql_action: SQL_ACTIONS = kwargs.get('sql_action', SQL_ACTIONS.INSERT)

        self._timeout = kwargs.get('timeout', None)
        self._timer: Timer = None
        self._data: list = list(data)
        self._result = None
        self._result_ready = False

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

    def get_select_data(self, **where):
        if self._sql_statement:
            return self._sql_statement.format(**where), None
        return select_sql(self._table.name, **where), None

    def get_insert_data(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        data = self._update_data(self._table, self._data, **updates)
        # if self._sql_statement:
        #     return self._sql_statement, [tuple(r) for r in data]
        return insert_sql(self._table.name, [t.name for t in self._table.fields]), [tuple(r) for r in data]

    def get_update_data(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        data = self._update_data(self._table, self._data, **updates)
        if self._sql_statement:
            return self._sql_statement, [tuple(r) for r in data]
        return update_sql(self._table.name, [t.name for t in self._table.fields]), [tuple(r) for r in data]

    def __str__(self):
        return f"{self.get_insert_data()}"

    @staticmethod
    def _raise_timeout(msg):
        def _():
            raise TimeoutError(msg)
        return _

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        if self._timeout:
            self._timer = Timer(self._timeout, self._raise_timeout(f"Timeout expired on query for table {self._table}"))
            self._timer.start()
        # if self._sql_action == SQL_ACTIONS.SELECT:
        #     return self.get_select_data(**updates)
        # if self._sql_action == SQL_ACTIONS.INSERT:
        return self.get_insert_data(**updates)
        # if self._sql_action == SQL_ACTIONS.UPDATE:
        #     return self.get_update_data(**updates)

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
