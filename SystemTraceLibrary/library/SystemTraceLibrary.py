import os
import re

from robot.api import logger
from robot.api.deco import library
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from SystemTraceLibrary.library.connection_manager import ConnectionManager, Listener
from SystemTraceLibrary.library.bi_manager import BIManager

from SystemTraceLibrary import builtin_plugins
from SystemTraceLibrary.api import db, Logger
from SystemTraceLibrary.model.runner_model import plugin_ssh_runner
from SystemTraceLibrary.utils import load_modules, plugins_table
from SystemTraceLibrary.version import VERSION


DEFAULT_SYSTEM_TRACE_LOG = 'logs'
DEFAULT_SYSTEM_LOG_FILE = 'SystemTraceLibrary.log'


@library(scope='GLOBAL', version=VERSION, listener=Listener())
class SystemTraceLibrary(ConnectionManager, BIManager):

    def __init__(self, location='logs', file_name=DEFAULT_SYSTEM_LOG_FILE, cumulative=False, custom_plugins=''):
        self.__doc__ = """
        = Trace System or any other data on linux hosts =
        == {} ==
        
        {}

        {}
        """.format(self.__class__.__name__, ConnectionManager.__doc__, BIManager.__doc__)

        ConnectionManager.__init__(self, location, file_name)
        BIManager.__init__(self, location)
        try:
            current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]
        except RobotNotRunningError:
            current_dir = ''

        self._start_suite_name = ''
        plugin_modules = load_modules(builtin_plugins, re.split(r'\s*,\s*', custom_plugins),
                                      base_path=current_dir, base_class=plugin_ssh_runner)
        db.PlugInService().update(**plugin_modules)

        plugins_table(db.PlugInService())

    def get_keyword_names(self):
        return ConnectionManager.get_keyword_names(self) + BIManager.get_keyword_names(self)

    def __del__(self):
        db.DataHandlerService().stop()

