from robot.utils import DotDict

from RemoteMonitorLibrary.api import model

CMD_TIME_FORMAT = DotDict(
    TimeReal="e",
    TimeKernel="S",
    TimeUser="U",
    TimeCPU="P",
    MemoryMaxResidentSize="M",
    MemoryAverage="t",
    MemoryAverageTotal="K",
    MemoryAverageProcessData="D",
    MemoryAverageProcessStack="p",
    MemoryAverageProcessShared="X",
    MemorySystemPageSize="Z",
    MemoryMajorPageFaults="F",
    MemoryMinorPageFaults="R",
    MemoryProcessSwapped="W",
    MemoryProcessContextSwitched="c",
    MemoryWait="w",
    IOInput="I",
    IOOutput="O",
    IOSocketRecieved="r",
    IOSocketSent="s",
    IOSignals="k",
    Rc="x",
    Command="C"
)


class TimeMeasurement(model.TimeReferencedTable):
    def __init__(self):
        model.TimeReferencedTable.__init__(self,
                                           name='TimeMeasurement',
                                           fields=[model.Field(f, model.FieldType.Int)
                                                   for f in CMD_TIME_FORMAT.keys()] +
                                                  [model.Field('OUTPUT_ID', model.FieldType.Int)])


class LinesCacheMap(model.Table):
    def __init__(self):
        model.Table.__init__(self, name=None,
                             fields=[
                                 model.Field('OUTPUT_REF', model.FieldType.Int),
                                 model.Field('ORDER_ID', model.FieldType.Int),
                                 model.Field('LINE_REF', model.FieldType.Int)],
                             foreign_keys=[model.ForeignKey('OUTPUT_REF', 'TimeMeasurement', 'OUTPUT_ID'),
                                           model.ForeignKey('LINE_REF', 'LinesCache', 'LINE_ID')],
                             queries=[model.Query('last_output_id', 'select max(OUTPUT_REF) from LinesCacheMap')])


class LinesCache(model.Table):
    def __init__(self):
        model.Table.__init__(self, name=None,
                             fields=[model.Field('LINE_ID',
                                                 model.FieldType.Int,
                                                 model.PrimaryKeys(True)),
                                     model.Field('Line')])


