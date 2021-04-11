# <package_title> (Version <VERSION>)

## Overview
<package_name> allow collect system data of target linux host during any Robotframework 
testing process being running

### Architecture
Main keyword library executing background python threads for SqlLite db node, separate theads for system trace collecting 
plugins
By default library contain 'aTopPlugIn'. 'atop' command being executing with predefined interval & its out put parsed as following:
#### aTop System Level
System level portion of 'atop' being storing in database, and later can be shown as chart in special html page
Link to it logged to robotframework regular log
#### aTop Process Level
TBD in future releases
#### PlugIn extension API
Library provide special API for create custom plugins (SystemTraceLibrary.api.[plugins, model])


## Installation

    python -m pip install robotframework-remote-monitor-library

## Usage

LibDoc: [Library documentation](docs/<package_name>.html)

### Test/Keywords within *.robot file

    *** Settings ***
    Library  <package_name> 
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

### PlugIn public API

SystemTraceLibrary allow creating extended plugins for trace customer purposes

#### Follow next guide:

##### Create python project 

    plug_in_python_project_folder

##### Create following files inside:

Main init project file for expose Plugin class

    __init__.py
        from .runner import MyPlugInName
        
        __all__ = [MyPlugInName.__name__]

##### Runner definition

    runner.py
        from <package_name>.api import plugins
        from .tables import plugin_table
        from .charts import plugin_chart
        
        class MyPlugInName(plugins.PlugInAPI):
            # If constractor override required, keep following signature 
            def __init__(self, parameters, data_handler, host_id, **kwargs):
                plugins.PlugInAPI.__init__(self, parameters, data_handler, host_id=host_id, **kwargs)
                self._my_own_var = ...

            @staticmethod
            def affiliated_tables() -> Iterable[model.Table]:
                return my_plugin_table(),
            
            @staticmethod
            def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
                return MyPlugInChart(),


##### Tables definition

    tables.py
        from <package_name>.api import model

        class my_plugin_table(model.TimeReferencedTable / model.Table):
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
##### Parser definition
   
    parser.py
         from <package_name>.api import plugins, model
         
         class my_parser(plugins.Parser):
            def __call__(*output) -> bool:
                table_template = self.table.template
                
                Data treatment                

                self.datahandler(model.DataUnit(self.table, your_data: [Iterable[Iterable]]

##### Chart definition

    charts.py
        from <package_name>.api.plugins import ChartAbstract
        
        class MyPlugInChart(ChartAbstract):
            pass
        
        Creating charts require familirisation with pandas & matplotlib

## Prerequisites
    Preinstalled: atop, time

## Supported OS
    All linux based system where atop supported

## Open issues
 - Add period histogram square or vertical line over system graph for indicate different period's start/stop 
   on same chart instead of create separated charts per period
