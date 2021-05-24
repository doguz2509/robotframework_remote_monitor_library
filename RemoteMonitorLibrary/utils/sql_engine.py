import logging
import os
import sqlite3
from threading import RLock
from typing import List

DEFAULT_DB_FILE = ":memory:"
DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
CREATE_TABLE_TEMPLATE = """CREATE TABLE IF NOT EXISTS {name} ({columns} {foreign_keys})"""
SELECT_TABLE = "SELECT {fields} FROM {table}"
SELECT_TABLE_WHERE = "SELECT {fields} FROM {table} WHERE {expression}"
INSERT_TABLE_TEMPLATE = "INSERT INTO {table} VALUES ({values})"
UPDATE_TABLE_TEMPLATE = "UPDATE {table}\nSET {columns}\nWHERE {where}"
FOREIGN_KEY_TEMPLATE = "FOREIGN KEY({local_field}) REFERENCES {foreign_table}({foreign_field})"


class SQL_DB:
    def __init__(self, location=None, file_name=None, cumulative=False, logger=logging):
        self._logger = logger
        self._lock = RLock()
        self._db_path = DEFAULT_DB_FILE
        self._conn = None
        self._cursor = None
        self._is_new = False
        self._init_db_connection(location, file_name, cumulative)
        self._table_cache = []

    def table_exist(self, name):
        return name in self._table_cache

    @property
    def is_new(self):
        return self._is_new

    @is_new.setter
    def is_new(self, value: bool):
        self._is_new = value

    @property
    def db_file(self):
        return self._db_path

    def _init_db_connection(self, location=None, file_name=None, cumulative=False):
        if location:
            if not os.path.exists(location):
                os.makedirs(location)
            file_name = f"{file_name or f'{self.__class__.__name__}.db'}"
            name, ext = os.path.splitext(file_name)
            file_name = f"{name}.db"
            self._db_path = os.path.join(location, file_name)
            if not cumulative:
                self._conn = None
                if self._clear_db(self._db_path):
                    self.is_new = True

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def _clear_db(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            self._logger.warning(f"Cannot remove db file - {path}; Continue with existing data")
            return False

    # def create_table(self, table_name, create_table_sql):
    #     try:
    #         self._cursor.execute(create_table_sql)
    #         self._conn.commit()
    #         self._table_cache.append(table_name)
    #     except Exception as e:
    #         raise RuntimeError(f"Cannot create table: Error{e}\nStatement: {create_table_sql}")
    #     else:
    #         return True

    def execute(self, sql: str, *args, **kwargs):
        _result = None
        with self._lock:
            # self._logger.debug("{}::execute: {}\nArgs: {}".format(self.__class__.__name__, sql, command))
            if args.__len__() == 0:
                self._cursor.execute(sql)
            elif isinstance(args[0], list):
                self._cursor.executemany(sql, args[0])
            elif isinstance(args, tuple):
                self._cursor.execute(sql, args)
            else:
                raise RuntimeError(
                    "{}::execute: Unknown input data type '{}' ({})".format(self.__class__.__name__, args,
                                                                            type(args).__name__))
            self._conn.commit()
            _result = self._cursor.fetchall()
            return _result

    @property
    def get_last_row_id(self):
        return self._cursor.lastrowid

    def query_last_row(self, table_name, ref_field):
        sql = f'select {ref_field} from {table_name} ORDER BY {ref_field} DESC LIMIT 1'
        return self.execute(sql)

    def close(self):
        self._conn.commit()
        self._conn.close()
        self._conn = None


def create_table_sql(name, columns: List, foreign_keys: List):
    return CREATE_TABLE_TEMPLATE.format(name=name,
                                        columns=',\n\t'.join(str(f) for f in columns),
                                        foreign_keys=',' + ',\n\t'.join(str(fk) for fk in foreign_keys)
                                        if len(foreign_keys) > 0 else '')


def select_sql(name, *fields, **filter_data):
    if len(fields) == 0:
        fields = ', '.join([f"{t}" for t in filter_data.keys()])
    else:
        fields = ', '.join([f"{t}" for t in fields])
    where = ' AND '.join("{} = {}".format(f, v if str(v).isdigit() else f"'{v}'") for f, v in filter_data.items())
    return f'SELECT {fields}\nFROM {name}\nWHERE {where}'


def insert_sql(table_name, columns):
    return INSERT_TABLE_TEMPLATE.format(table=table_name, values=",".join(['?'] * len(columns)))


def update_sql(name, *columns, **where):
    return UPDATE_TABLE_TEMPLATE.format(table=name,
                                        columns=",\n\t".join([f"{c} = ?" for c in columns]),
                                        where=' AND '.join(
                                            "{} = {}".format(f, v if str(v).isdigit() else f'"{v}"') for f, v in
                                            where.items()))


__all__ = [
    'SQL_DB',
    'create_table_sql',
    'insert_sql',
    'select_sql',
    'update_sql',
    'DB_DATETIME_FORMAT',
    'FOREIGN_KEY_TEMPLATE'
]
