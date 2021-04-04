# System Trace Library


## Installation

    python -m pip install robotframework_system_trace_library

## Usage

### Test/Keywords within *.robot file

    *** Settings ***
    Library  SystemTraceLibrary 
    ...     [location (Default: logs)] 
    ...     [file_name (Default: system_trace.db)]
    ...     [cumulative (Default: False)]
    ...     [custom_plugins (Default: None)]
    
    Suite Setup  run keywords  create host connection  ${HOST}  ${USER}  ${PASSWORD}  [${PORT} (Default: 22)] 
    ...                 [alias=${SUITE_NAME} (Default: user@host)]
    ...          AND  start trace plugin  aTopPlugIn  interval=1s
    Test Setup   Start period  ${TEST_NAME}
    Test Teardown  run keywords  Stop period   ${TEST_NAME}
    ...             AND  generate module statistics  ${TEST_NAME}
    Suite Teardown  Close host connection  alias=${SUITE_NAME}

    *** Tests ***
    Test
        Do something here

### PlugIn extending

SystemTraceLibrary allow creating extended plugins for trace customer purposes

#### Follow next guide:

##### Create python project 

    plug_in_python_project_folder

##### Create following files inside:

Main init project file for expose Plugin class

    __init__.py
        from .runner import PlugInName
        
        __all__ = [PlugInName.__name__]

##### Runner definition

    runner.py
        from system_trace.api import plugins
        from .tables import plugin_table
        from .charts import plugin_chart
        
        class PlugInName(plugins.PlugInAPI):
            # If constractor override required, keep following signature 
            def __init__(self, parameters, data_handler, host_id, **kwargs):
                plugins.PlugInAPI.__init__(self, parameters, data_handler, host_id=host_id, **kwargs)
                self._my_own_var = ...

            @staticmethod
            def affiliated_tables() -> Iterable[model.Table]:
                return plugin_table(),
            
            @staticmethod
            def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
                return aTopSystemLevelChart('CPU')

    @staticmethod
    def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
        return aTopSystemLevelChart('CPU'),

##### Tables definition

    tables.py
        from system_trace.api import model

        class plugin_table(model.TimeReferencedTable / model.Table):
            def __init__(self):
                model.TimeReferencedTable.__init__(self, name='plugin_table',
                                                   fields=[model.Field('field01'),
                                                           model.Field('field02'),
                                                           ...],
                                                   queries=[model.Query('name', 'select * from table_name where field01 = {}')]
                                                   )
        
        !!! PAY ATTENTION - TimeReferencedTable automatically add fields for reference table entries to time line 
        mechanism 
        In case it not requires, use model.Table base class

##### Chart definition

    charts.py
        from system_trace.api.plugins import ChartAbstract
        
        class plugin_chart(ChartAbstract):
            pass
        
        Creating charts require familirisation with pandas & matplotlib


