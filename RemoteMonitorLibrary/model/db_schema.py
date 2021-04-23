from collections import namedtuple
from enum import Enum
from typing import List, Iterable, Tuple, AnyStr

from robot.utils import DotDict

from RemoteMonitorLibrary.utils import sql


class FieldType(Enum):
    Int = 'INTEGER'
    Text = 'TEXT'
    Real = 'REAL'


class PrimaryKeys:
    def __init__(self, auto_increment=False):
        self._auto_increment = auto_increment

    def __str__(self):
        return ' PRIMARY KEY' + ' AUTOINCREMENT' if self._auto_increment else ''


class Field:
    def __init__(self, name, type_: FieldType = None, primary_key: PrimaryKeys = None,
                 not_null=False, unique=False):
        """
        Table field definition
        :param name: Table name string
        :param type_: field type (INTEGER, TEXT, REAL)
        """

        self._name: str = name
        self._type: FieldType = type_ or FieldType.Text
        self._primary_key = primary_key
        self._not_null = not_null
        self._unique = unique

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def primary_key(self):
        return f" {self._primary_key}" if self._primary_key else ''

    @property
    def not_null(self):
        return ' NOT NULL' if self._not_null else ''

    @property
    def unique(self):
        return ' UNIQUE' if self._unique else ''

    def __str__(self):
        return f"{self.name} {self.type.value}{self.not_null}{self.unique}{self.primary_key}"


class Query:
    def __init__(self, name: str, sql: str):
        """
        Query assigned for Table
        :param name: query name string
        :param sql: SQL statement in python format (Mandatory variables)
        """
        self._name = name
        self._sql = sql

    @property
    def name(self):
        return self._name

    @property
    def sql(self):
        return self._sql

    def __call__(self, *args, **kwargs):
        return self.sql.format(*args, **kwargs)


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

    def __hash__(self):
        return hash(str(self))

    def clone(self):
        return type(self)(self.own_field, self.foreign_table, self.foreign_field)


class Table(object):
    def __init__(self, name=None, fields: Iterable[Field] = [], queries: Iterable[Query] = [],
                 foreign_keys: List[ForeignKey] = []):
        self._name = name or self.__class__.__name__
        self._fields = tuple()
        for f in fields:
            self.add_field(f)
        self._foreign_keys = tuple()
        for fk in foreign_keys:
            self.add_foreign_key(fk)
        self._queries: DotDict[str, Query] = DotDict()
        for query in queries or []:
            self._queries[query.name] = query

    @property
    def template(self):
        return namedtuple(self.name, (f.name for f in self.fields))

    @property
    def fields(self) -> Tuple:
        return self._fields

    def add_field(self, field: Field):
        assert field not in self.fields, f"Field '{field}' already exist"
        self._fields = tuple(list(self.fields) + [field])

    @property
    def columns(self) -> List[AnyStr]:
        return [f.name for f in self.fields]

    def __str__(self):
        return f"{self.name}: {', '.join(self.columns)}"

    @property
    def name(self):
        return self._name

    @property
    def queries(self):
        return self._queries

    @property
    def foreign_keys(self) -> Tuple:
        return self._foreign_keys

    def add_foreign_key(self, fk: ForeignKey):
        assert fk not in self.fields, f"Foreign Key '{fk}' already exist"
        self._foreign_keys = tuple(list(self._foreign_keys) + [fk])


