from typing import Iterable

from RemoteMonitorLibrary.model.schema_model import Table, Field, Query, ForeignKey, FieldType, DataUnit


class TimeReferencedTable(Table):
    def __init__(self, name, fields: Iterable[Field], queries=None, foreign_keys=None):
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


__all__ = [
    'TimeReferencedTable',
    'Table',
    'Field',
    'FieldType',
    'ForeignKey',
    'Query',
    'DataUnit'
]


