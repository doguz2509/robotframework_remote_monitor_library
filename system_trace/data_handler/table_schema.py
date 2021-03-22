import os
from collections import OrderedDict
from typing import Dict, Mapping, Tuple

import yaml
from robot.api import logger
from robot.utils import DotDict

from system_trace.utils import Singleton
from system_trace.utils.sql_engine import SQL_DB, FOREIGN_KEY_TEMPLATE, CREATE_TABLE_TEMPLATE


class _FormatCallback:
    def __init__(self, _name, sql_text, *args, **kwargs):
        self.name = _name
        self.sql_text = sql_text
        self.arg_template = args
        self.kwargs_template = kwargs

    def __call__(self, *args, **kwargs):
        try:
            return self.sql_text.format(*args, **kwargs)
        except Exception as e:
            raise type(e)("Table '{}; Error format sql -> {}\n{}".format(self.name, e, self.sql_text))


class ReadOnlyKeyDict(OrderedDict):
    def __init__(self, *keys):
        for key in keys:
            OrderedDict.__setitem__(self, key, None)

    def set(self, *values):
        assert len(values) == len(self.keys()), f"Values count ({len(values)}) not match keys ({self.keys()})"
        new_item = self.clone()
        for i, key in enumerate(new_item.keys()):
            new_item[key] = values[i]
        return new_item

    def __setattr__(self, key, value):
        if key not in self.keys():
            raise ValueError("Key change locked")
        OrderedDict.__setitem__(self, key, value)

    def __delattr__(self, item):
        raise ValueError("Key change locked")

    def clone(self):
        return type(self)(*self.keys())


class TableSchema:
    FIELD_TYPES = {'INTEGER': int, 'TEXT': str, 'BLOB': bytes, 'REAL': float, 'NUMERIC': float}

    def __init__(self, name=None):
        self._name = name or self.__class__.__name__
        self._columns = []
        self._rows = []
        for name, type_ in self.fields.items():
            self._column_add(name, type_)
        self._foreign_keys_sql = [FOREIGN_KEY_TEMPLATE.format(local_field=of, foreign_table=ft, foreign_field=ff)
                                  for of, (ft, ff) in self.foreign_keys_dict.items()]

    @property
    def name(self):
        return self._name

    @property
    def fields(self) -> OrderedDict:
        return self._fields

    @property
    def foreign_keys(self) -> list:
        return [FOREIGN_KEY_TEMPLATE.format(local_field=of, foreign_table=ft, foreign_field=ff)
                for of, (ft, ff) in self.foreign_keys_dict.items()]

    @property
    def foreign_keys_dict(self) -> Mapping[str, Tuple[str, str]]:
        return self._foreign_keys

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            raise exc_type(exc_val, exc_tb)

    def _column_add(self, name, type_: str, index=-1):
        if isinstance(type_, tuple):
            assert type_[0].upper() in self.FIELD_TYPES.keys(), \
                f"Field type not match ({type_} [Allowed: {self.FIELD_TYPES}]"
        else:
            assert type_.upper() in self.FIELD_TYPES.keys(), \
                f"Field type not match ({type_} [Allowed: {self.FIELD_TYPES}]"
        if index == -1:
            self._columns.append((name, type_))
        else:
            self._columns.insert(index, (name, type_))

    def load(self, *rows):
        err = []
        for i, row in enumerate(rows):
            try:
                if not isinstance(row, ReadOnlyKeyDict):
                    row = self.column_template.set(*row)
                self.row_add(**row)
            except Exception as e:
                err.append(f"Line {i}: '{row}' raising error: {e}")
        assert len(err) == 0, "Following lines broken:\n{}".format('\n'.join([str(er) for er in err]))
        return self

    def row_add(self, **fields):
        cells = []
        for name, type_ in self._columns:
            try:
                if isinstance(type_, tuple):
                    cell_v = self.FIELD_TYPES[type_[0]](fields.get(name))
                else:
                    cell_v = self.FIELD_TYPES[type_](fields.get(name))
                cells.append(cell_v)
            except Exception as e:
                raise TypeError(f"Value '{fields.get(name)}' not match type {type_}")
        self._rows.append(cells)
        return self

    @property
    def rows(self):
        return self._rows

    def update(self, column, value):
        col_id = [i for i, _ in self._columns].index(column)
        for row_id in range(0, len(self._rows)):
            self._rows[row_id][col_id] = value

    @property
    def columns_list(self):
        return [col_name for col_name, _ in self._columns]

    @property
    def column_template(self):
        return ReadOnlyKeyDict(*self.columns_list)

    @property
    def insert_sql(self):
        fields_names = self.columns_list
        columns_text = "{} ({})".format(self.name, ",".join(fields_names))
        value_text = "VALUES ({})".format(",".join(['?'] * len(fields_names)))
        return "INSERT INTO {table} {values}".format(table=columns_text, values=value_text)

    def get_key_to_table(self, column):
        try:
            col_name = [col_name for col_name, _ in self._columns][0]
        except IndexError:
            raise IndexError(f"Column '{column}' no exists")
        else:
            return self.name, col_name

    @property
    def create_table_sql(self):
        columns_text = ",\n".join(["{} {}".format(
            name,
            f"{options[0]} PRIMARY KEY" if isinstance(options, tuple) else options) for name, options in self._columns])
        return CREATE_TABLE_TEMPLATE.format(
            name=self.name,
            columns=columns_text,
            foreign_keys=',\n{}'.format(',\n'.join(self.foreign_keys)) if len(self.foreign_keys) > 0 else ''
        )


def _get_field_list(table_name, table, defaults) -> OrderedDict:
    fields = OrderedDict()
    fields_conf = table.get('fields', None)
    assert len(fields_conf) > 0, f"No fields provided for table '{table_name}'"
    for field in fields_conf:
        type_ = field.get('type', defaults.get('type'))
        fields.update({field.get('name'): (type_,) if field.get('key', False) else type_})
    return fields


def _get_queries(table_name, table):
    queries = {}
    queries_conf = table.get('queries') or {}
    for query_name, query_conf in queries_conf.items():
        func = query_conf.get('function')
        arg = query_conf.get('args', [])
        kwarg = query_conf.get('kwargs', {})
        sql = query_conf.get('sql')
        if func == 'format':
            queries.update({query_name: _FormatCallback(table_name, sql, *arg, *kwarg)})
        else:
            queries.update({query_name: sql})
    return queries


def _get_foreign_keys(table, tables):
    foreign_keys = {}
    foreign_keys_conf = table.get('foreign_keys', {}) or {}
    for ref_field, ref_to_table in foreign_keys_conf.items():
        ref_table_name = ref_to_table.get('table')
        ref_table_field = ref_to_table.get('field')
        assert ref_table_name in tables.keys(), \
            f"Table '{ref_table_name}' still not initialised; Order table order in Yaml"
        foreign_keys.update({f"{ref_field}": tables.get(ref_table_name)().get_key_to_table(ref_table_field)})
    return foreign_keys


def _init(self, name=None):
    TableSchema.__init__(self, name)


def generate_schema(schema) -> Dict[str, type]:
    tables: OrderedDict[str, type] = OrderedDict()
    defaults = schema.get('defaults', {})

    tables_conf = schema.get('tables', None)

    for table in tables_conf:
        name = table.get('name')
        assert name, f"Table name missing:\n{table}"
        try:
            fields = _get_field_list(name, table, defaults)
            queries = _get_queries(name, table)
            foreign_keys = _get_foreign_keys(table, tables)
            _new_fields = {"__init__": _init, '_fields': fields, '_foreign_keys': foreign_keys}
            _new_fields.update(**queries)
            new_type = type(name, (TableSchema,), _new_fields)

            tables.update({name: new_type})
        except Exception as e:
            print(f"{e}")

    return tables


class DotTypedDict(DotDict):
    def __getattr__(self, item):
        return DotDict.__getattr__(self, item)()


DEFAULT_YAML = r"statistic_db_schema.yaml"


@Singleton
class _bb_factory:
    def __init__(self, path=None):
        self._data = DotTypedDict()
        if path is None:
            _path, file = os.path.split(__file__)
            _path = os.path.join(_path, DEFAULT_YAML)
        else:
            _path = path
        self._path = _path
        self.load()

    @property
    def tables(self):
        return self._data

    def load(self):
        if len(self._data) > 0:
            print("Already loaded")
            return
        assert os.path.exists(self._path), f"File not accessible or not exist '{self._path}'"

        with open(self._path, 'r') as sr:
            conf = yaml.safe_load(sr)
            for name, table in generate_schema(conf).items():
                self._data.update({name: table})
            logger.debug("Loading from yaml '{}' completed;\nTable list:\n\t{}".format(
                self._path,
                '\n\t'.join([f"{i}. {t}" for i, t in enumerate(self._data.keys())]))
            )


def init_db_schema(path=None):
    _bb_factory(path).load()


TableFactory = _bb_factory().tables

