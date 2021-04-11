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
                                                   for f in CMD_TIME_FORMAT.keys()] + [model.Field('OUTPUT_REF')],
                                           foreign_keys=[model.ForeignKey('OUTPUT_REF', 'OutputCache', 'OUTPUT_ID')])

