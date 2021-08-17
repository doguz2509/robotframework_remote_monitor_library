from RemoteMonitorLibrary.model.db_schema import Table, Field, FieldType, PrimaryKeys, Query, ForeignKey


class TraceHost(Table):
    def __init__(self):
        super().__init__(name='TraceHost')
        self.add_field(Field('HOST_ID', FieldType.Int, PrimaryKeys(True)))
        self.add_field(Field('HostName', FieldType.Text, unique=True))


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
    FIELDS_TYPES = [
        ('asctime', FieldType.Int),
        ('levelname', FieldType.Text),
        ('threadName', FieldType.Text),
        ('module', FieldType.Text),
        ('funcName', FieldType.Text),
        ('msg', FieldType.Text),
        ('lineno', FieldType.Int),
        ('exc_text', FieldType.Text),
        ('process', FieldType.Int),
        ('thread', FieldType.Text),
        ('levelno', FieldType.Int),
        ('name', FieldType.Text)]

    _shown_fields = [0, 1, 2, 3, 4, 5]

    def __init__(self):
        super().__init__()
        for i in self._shown_fields:
            f, t = self.FIELDS_TYPES[i]
            self.add_field(Field(f.capitalize(), t))

    # initial_sql = """CREATE TABLE IF NOT EXISTS log(TimeStamp TEXT, Source TEXT, LogLevel INT, LogLevelName TEXT,
    #                                                 Message TEXT, Module TEXT, FuncName TEXT, LineNo INT,
    #                                                 Exception TEXT, Process INT, Thread TEXT, ThreadName TEXT)"""
    # insertion_sql = """INSERT INTO log(TimeStamp, Source, LogLevel, LogLevelName, Message, Module, FuncName, LineNo,
    #                         Exception, Process, Thread, ThreadName)
    #                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    #                    """
    #

    @staticmethod
    def format_record(record):
        _result_record = []
        for i in log._shown_fields:
            f, _ = log.FIELDS_TYPES[i]
            assert hasattr(record, f)
            _result_record.append(getattr(record, f))
        return tuple(_result_record)
