from RemoteMonitorLibrary.model.db_schema import Table, Field, FieldType, PrimaryKeys, Query, ForeignKey


class TraceHost(Table):
    def __init__(self):
        super().__init__(name='TraceHost',
                         fields=[Field('HOST_ID', FieldType.Int, PrimaryKeys(True)), Field('HostName')])


class Points(Table):
    def __init__(self):
        Table.__init__(self, name='Points',
                       fields=(Field('HOST_REF', FieldType.Int), Field('PointName'), Field('Start'), Field('End')),
                       foreign_keys=[ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID')],
                       queries=[Query('select_state', """SELECT {} FROM Points
                       WHERE HOST_REF = {} AND PointName = '{}'""")])


class LinesCacheMap(Table):
    def __init__(self):
        super().__init__(fields=[Field('OUTPUT_REF', FieldType.Int), Field('ORDER_ID', FieldType.Int),
                                 Field('LINE_REF', FieldType.Int)],
                         foreign_keys=[ForeignKey('OUTPUT_REF', 'TimeMeasurement', 'OUTPUT_ID'),
                                       ForeignKey('LINE_REF', 'LinesCache', 'LINE_ID')],
                         queries=[Query('last_output_id', 'select max(OUTPUT_REF) from LinesCacheMap')])


class LinesCache(Table):
    def __init__(self):
        Table.__init__(self, fields=[
            Field('LINE_ID', FieldType.Int, PrimaryKeys(True)),
            Field('HashTag', unique=True),
            Field('Line')])


class PlugInTable(Table):
    def add_time_reference(self):
        self.add_field(Field('HOST_REF', FieldType.Int))
        self.add_field(Field('TL_REF', FieldType.Int))
        self.add_foreign_key(ForeignKey('TL_REF', 'TimeLine', 'TL_ID'))
        self.add_foreign_key(ForeignKey('HOST_REF', 'TraceHost', 'HOST_ID'))

    def add_output_cache_reference(self):
        self.add_field(Field('OUTPUT_REF', FieldType.Int))
        self.add_foreign_key(ForeignKey('OUTPUT_REF', 'LinesCacheMap', 'OUTPUT_REF'))


class TimeLine(Table):
    def __init__(self):
        Table.__init__(self, name='TimeLine',
                       fields=[Field('TL_ID', FieldType.Int, PrimaryKeys(True)), Field('TimeStamp', FieldType.Text)],
                       queries=[Query('select_last', 'SELECT TL_ID FROM TimeLine WHERE TimeStamp == "{timestamp}"')]
                       )


class log(PlugInTable):
    def __init__(self):
        super().__init__(fields=[Field('TimeStamp'),
                                 Field('Source'),
                                 Field('LogLevel', FieldType.Int),
                                 Field('LogLevelName'),
                                 Field('Message'),
                                 Field('Module'),
                                 Field('FuncName'),
                                 Field('LineNo', FieldType.Int),
                                 Field('Exception'),
                                 Field('Process', FieldType.Int),
                                 Field('Thread'),
                                 Field('ThreadName')])

    initial_sql = """CREATE TABLE IF NOT EXISTS log(TimeStamp TEXT, Source TEXT, LogLevel INT, LogLevelName TEXT,
                                                    Message TEXT, Module TEXT, FuncName TEXT, LineNo INT,
                                                    Exception TEXT, Process INT, Thread TEXT, ThreadName TEXT)"""

    INSERT_FIELDS = ('asctime', 'name', 'levelno', 'levelname', 'msg', 'module',
                     'funcName', 'lineno', 'exc_text', 'process', 'thread', 'threadName')

    insertion_sql = """INSERT INTO log(TimeStamp, Source, LogLevel, LogLevelName, Message, Module, FuncName, LineNo, 
                            Exception, Process, Thread, ThreadName)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       """