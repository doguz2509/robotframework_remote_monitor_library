from SystemTraceLibrary.api import model


class atop_system_level_table(model.TimeReferencedTable):
    def __init__(self):
        model.TimeReferencedTable.__init__(self, name='atop_system_level',
                                           fields=[model.Field('Type'),
                                                   model.Field('DataMap'),
                                                   model.Field('Col1', model.FieldType.Real),
                                                   model.Field('Col2', model.FieldType.Real),
                                                   model.Field('Col3', model.FieldType.Real),
                                                   model.Field('Col4', model.FieldType.Real),
                                                   model.Field('Col5', model.FieldType.Real),
                                                   model.Field('SUB_ID')])
