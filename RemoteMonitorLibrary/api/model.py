from abc import ABCMeta
from typing import Iterable

from RemoteMonitorLibrary.model.db_schema import Table, Field, Query, PrimaryKeys, ForeignKey, FieldType, DataUnit


class TimeReferencedTable(Table, metaclass=ABCMeta):
    def __init__(self, name=None, fields: Iterable[Field] = [], queries=[], foreign_keys=[]):
        fields, foreign_keys = self._add_timeline_reference(fields, foreign_keys)
        Table.__init__(self, name, fields, queries, foreign_keys)

    @staticmethod
    def _add_timeline_reference(fields: Iterable[Field], foreign_keys=None):
        fields = list(fields)
        fields.insert(0, Field('HOST_REF', FieldType.Int))
        fields.insert(1, Field('TL_REF', FieldType.Int))
        foreign_keys = list(foreign_keys) if foreign_keys else []
        foreign_keys.insert(0, ForeignKey('TL_REF', 'TimeLine', 'TL_ID'))
        foreign_keys.insert(0, ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID'))
        return fields, foreign_keys


class OutputCacheTable(Table, metaclass=ABCMeta):
    def __init__(self, name=None, fields=None, queries=[], foreign_keys=[]):
        if fields is None:
            fields = []
        fields, foreign_keys = self._add_output_reference(fields, foreign_keys)
        Table.__init__(self, name, fields, queries, foreign_keys)

    @staticmethod
    def _add_output_reference(fields: Iterable[Field], foreign_keys=[]):
        fields = list(fields)
        fields.append(Field('OUTPUT_REF', FieldType.Int))
        if foreign_keys:
            foreign_keys = list(foreign_keys)
            foreign_keys.append(ForeignKey('OUTPUT_REF', 'LinesCacheMap', 'OUTPUT_REF'))
        return fields, foreign_keys


__all__ = [
    'Table',
    'Field',
    'FieldType',
    'ForeignKey',
    'PrimaryKeys',
    'Query',
    'DataUnit',
    'TimeReferencedTable',
    'OutputCacheTable'
]


