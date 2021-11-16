# Remote Monitor Library (Version 2.6.11)

## Overview
RemoteMonitorLibrary allow collect system data of target linux host during any Robotframework 
testing process being running

### Architecture
Main keyword library executing background python threads for SqlLite db node, separate threads for system trace collecting 
plugins
By default library contain 'aTop'. 'atop' command being executing with predefined interval & its out put parsed as following:
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

LibDoc: [Library documentation](RemoteMonitorLibrary.html)

### Test/Keywords within *.robot file

    *** Settings ***
    Library  RemoteMonitorLibrary 
    ...     [location (Default: logs)] 
    ...     [file_name (Default: system_trace.db)]
    ...     [cumulative (Default: False)]
    ...     [custom_plugins (Default: None)]
    
    Suite Setup  run keywords  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}  [${PORT} (Default: 22)] 
    ...                 [alias=${SUITE_NAME} (Default: user@host)]
    ...          AND  Start monitor plugin  aTop  interval=1s
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
        from .pluin_file import MyPlugInName
        
        __all__ = [MyPlugInName.__name__]

##### Runner definition

     from RemoteMonitorLibrary.api import plugins
     
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

     from RemoteMonitorLibrary.api import model

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

    from RemoteMonitorLibrary.api import plugins, model
   
    class my_parser(plugins.Parser):
         def __call__(*output) -> bool:
            table_template = self.table.template
          
            your_data = []
            for item in <data samples>:
               yuor_data.append(table_template(*item))
            
            data_unit = model.DataUnit(self.table, *your_data)
            self.datahandler(data_unit)

##### Chart definition

     from RemoteMonitorLibrary.api.plugins import ChartAbstract
     
     class MyPlugInChart(ChartAbstract):
         pass
     
     Creating charts require familirisation with pandas & matplotlib

## Prerequisites
    Preinstalled: atop, time installed on remote host, ssh enabled

## Supported OS
    All linux based system where atop supported

## Open issues
 - Add period histogram square or vertical line over system graph for indicate different period's start/stop 
   on same chart instead of create separated charts per period
