import os
import re

from robot.api import logger
from robot.api.deco import library
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from RemoteMonitorLibrary import plugins
from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.library import robotframework_portal_addon
from RemoteMonitorLibrary.library.bi_keywords import BIKeywords
from RemoteMonitorLibrary.library.connection_keywords import ConnectionKeywords
from RemoteMonitorLibrary.runner import SSHLibraryPlugInWrapper
from RemoteMonitorLibrary.utils import load_modules, print_plugins_table
from RemoteMonitorLibrary.version import VERSION

DEFAULT_SYSTEM_TRACE_LOG = 'logs'
DEFAULT_SYSTEM_LOG_FILE = 'RemoteMonitorLibrary.log'


@library(scope='GLOBAL', version=VERSION)
class RemoteMonitorLibrary(ConnectionKeywords, BIKeywords):

    def __init__(self, location=DEFAULT_SYSTEM_TRACE_LOG, file_name=DEFAULT_SYSTEM_LOG_FILE, custom_plugins='',
                 **kwargs):
        self.__doc__ = """
        
        Remote Monitor CPU (wirth aTop), & Process (with Time) or any other data on linux hosts with custom plugins
        
        Allow periodical execution of commands set on one or more linux hosts with collecting data within SQL db following with some BI activity
        
        For current phase only data presentation in charts available.
        
        == Keywords & Usage ==
        
        {}

        {}
        
        == BuiltIn plugins ==
        
        System support following plugins:
        
        {}
        
        {} 
        
        {}
        
        {}
        """.format(ConnectionKeywords.__doc__,
                   BIKeywords.__doc__,
                   plugins.atop_plugin.__doc__,
                   plugins.sshlibrary_plugin.__doc__,
                   plugins.time_plugin.__doc__,
                   robotframework_portal_addon.__doc__
                   )

        ConnectionKeywords.__init__(self, location, file_name, **kwargs)
        BIKeywords.__init__(self, location)
        try:
            current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]
        except RobotNotRunningError:
            current_dir = ''

        self._start_suite_name = ''
        plugin_modules = load_modules(plugins, *[pl for pl in re.split(r'\s*,\s*', custom_plugins) if pl != ''],
                                      base_path=current_dir, base_class=SSHLibraryPlugInWrapper)
        db.PlugInService().update(**plugin_modules)
        print_plugins_table(db.PlugInService())
        lib_path, lib_file = os.path.split(__file__)
        lib_name, ext = os.path.splitext(lib_file)
        lib_doc_file = f"{lib_name}.html"
        logger.warn(f'{self.__class__.__name__} <a href="{os.path.join(lib_path, lib_doc_file)}">LibDoc</a>', html=True)

    def get_keyword_names(self):
        return ConnectionKeywords.get_keyword_names(self) + BIKeywords.get_keyword_names(self)


