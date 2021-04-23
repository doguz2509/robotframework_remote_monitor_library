from typing import Tuple, Iterable

from robot.utils import DotDict

from RemoteMonitorLibrary.api.db import PlugInTable, DataUnit, CacheLines
from RemoteMonitorLibrary.model.db_schema import Table, Field, Query, PrimaryKeys, ForeignKey, FieldType


class DataRowUnitWithOutput(DataUnit):
    def __init__(self, table, *data, **kwargs):
        super().__init__(table, *data)
        self._output = kwargs.get('output', None)
        assert self._output, "Output not provided"

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        output_ref = CacheLines().upload(self._output)
        for i in range(0, len(self._data)):
            _template = DotDict(self._data[i]._asdict())
            _template.update({'OUTPUT_REF': output_ref})
            self._data[i] = self.table.template(*_template.values())
        return super().__call__(**updates)


__all__ = [
    'Table',
    'PlugInTable',
    'Field',
    'FieldType',
    'ForeignKey',
    'PrimaryKeys',
    'Query',
    'DataUnit',
    'DataRowUnitWithOutput'
]
