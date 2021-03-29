from collections import namedtuple
from enum import Enum
from typing import List, Iterable

from robot.utils import DotDict

from system_trace.utils import Singleton
from system_trace.utils.sql_engine import FOREIGN_KEY_TEMPLATE


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
        :param sql: SQL statement in python format
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
        return FOREIGN_KEY_TEMPLATE.format(local_field=self.own_field,
                                           foreign_table=self.foreign_table,
                                           foreign_field=self.foreign_field)

    def clone(self):
        return type(self)(self.own_field, self.foreign_table, self.foreign_field)


class Table(object):
    def __init__(self, name=None, fields: Iterable[Field] = None, queries: Iterable[Query] = None,
                 foreign_keys: List[ForeignKey] = None):
        self._name = name or self.__class__.__name__
        self._fields: List[Field] = fields or []
        self._queries: List[Query] = queries or []
        self._foreign_keys: List[ForeignKey] = foreign_keys or []

    @property
    def template(self):
        return namedtuple(self.name, (f.name for f in self.fields))

    @property
    def fields(self):
        return self._fields

    @property
    def name(self):
        return self._name

    @property
    def queries(self):
        return self._queries

    @property
    def foreign_keys(self):
        return self._foreign_keys


class Sessions(Table):
    def __init__(self):
        Table.__init__(self, name=None,
                       fields=[Field('SESSION_ID', FieldType.Int, True),
                               Field('Start'), Field('End'), Field('Title')])


class TimeLine(Table):
    def __init__(self):
        Table.__init__(self, name=None,
                       fields=[Field('TL_ID', FieldType.Int, True), Field('TimeStamp', FieldType.Text)])


TIME_REFERENCE_FIELD = Field('TL_REF', FieldType.Int)
FOREIGN_KEY = ForeignKey('TL_REF', 'TimeLine', 'TL_ID')


@Singleton
class DbSchema:
    def __init__(self):
        self._data = DotDict(Sessions=Sessions(), TimeLine=TimeLine())

    @property
    def tables(self):
        return self._data

    def register_table(self, table: Table):
        table.fields.insert(0, TIME_REFERENCE_FIELD)
        table.foreign_keys.insert(0, FOREIGN_KEY.clone())
        self._data[table.name] = table


