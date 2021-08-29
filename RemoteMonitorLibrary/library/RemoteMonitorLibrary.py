import os
import re

from robot.api.deco import library
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from RemoteMonitorLibrary import plugins_modules
from RemoteMonitorLibrary.api import services
from RemoteMonitorLibrary.api.services import RegistryModule
from RemoteMonitorLibrary.library import robotframework_portal_addon
from RemoteMonitorLibrary.library.bi_keywords import BIKeywords
from RemoteMonitorLibrary.library.connection_keywords import ConnectionKeywords
from RemoteMonitorLibrary.model.runner_model import plugin_runner_abstract
from RemoteMonitorLibrary.utils import load_modules, print_plugins_table
from RemoteMonitorLibrary.utils import logger
from RemoteMonitorLibrary.version import VERSION

DEFAULT_SYSTEM_TRACE_LOG = 'logs'
DEFAULT_SYSTEM_LOG_FILE = 'RemoteMonitorLibrary.log'


@library(scope='GLOBAL', version=VERSION)
class RemoteMonitorLibrary(ConnectionKeywords, BIKeywords):

    def __init__(self, location=DEFAULT_SYSTEM_TRACE_LOG, file_name=DEFAULT_SYSTEM_LOG_FILE,
                 custom_plugins='', **kwargs):
        self.__doc__ = """
        
        Remote Monitor CPU (wirth aTop), & Process (with Time) or any other data on linux hosts with custom plugins_modules
        
        Allow periodical execution of commands set on one or more linux hosts with collecting data within SQL db following with some BI activity
        
        For current phase only data presentation in charts available.
        
        == Keywords & Usage ==
        - log_to_db     : logger will store logs into db (table: log; Will cause db file size size growing)
        
        {}

        {}
        
        == BuiltIn plugins_modules ==
        
        System support following plugins_modules:
        
        {}
        
        {} 
        
        {}
        
        {}
        """.format(ConnectionKeywords.__doc__,
                   BIKeywords.__doc__,
                   plugins_modules.atop_plugin.__doc__,
                   plugins_modules.sshlibrary_plugin.__doc__,
                   plugins_modules.time_plugin.__doc__,
                   robotframework_portal_addon.__doc__
                   )

        file_name = f"{file_name}.log" if not file_name.endswith('.log') else file_name

        ConnectionKeywords.__init__(self, location, file_name, **kwargs)
        BIKeywords.__init__(self, location)
        try:
            current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]
        except RobotNotRunningError:
            current_dir = ''

        custom_plugins_list = load_modules(plugins_modules,
                                           *[pl for pl in re.split(r'\s*,\s*', custom_plugins) if pl != ''],
                                           base_path=current_dir, base_class=(plugin_runner_abstract, RegistryModule))

        services.PlugInService().update(
            **{k: v for k, v in custom_plugins_list.items() if issubclass(v, plugin_runner_abstract)}
        )
        services.ModulesRegistryService().update(
            **{k: v for k, v in custom_plugins_list.items() if issubclass(v, RegistryModule)}
        )

        print_plugins_table(services.PlugInService())
        doc_path = self._get_doc_link()
        logger.warn(f'{self.__class__.__name__} <a href="{doc_path}">LibDoc</a>', html=True)

    @staticmethod
    def _get_doc_link():
        lib_path, lib_file = os.path.split(__file__)
        lib_name, ext = os.path.splitext(lib_file)
        lib_doc_file = f"{lib_name}.html"
        return os.path.join(lib_path, lib_doc_file)

    def get_keyword_names(self):
        return ConnectionKeywords.get_keyword_names(self) + BIKeywords.get_keyword_names(self)
