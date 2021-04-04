import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.running import TestSuite

from .data_view import data_view_and_analyse
from SystemTraceLibrary import builtin_plugins
from SystemTraceLibrary.api import Logger, db
from SystemTraceLibrary.model.host_registry_model import HostRegistryCache, HostModule
from SystemTraceLibrary.model.runner_model import plugin_ssh_runner
from SystemTraceLibrary.utils import load_modules, get_error_info
from ..utils.load_modules import plugins_table
from SystemTraceLibrary.utils.sql_engine import insert_sql, update_sql, DB_DATETIME_FORMAT


DEFAULT_SYSTEM_TRACE_LOG = 'logs'
DEFAULT_SYSTEM_LOG_FILE = 'SystemTraceLibrary.log'


class base_keywords(data_view_and_analyse):
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, location='logs', file_name=DEFAULT_SYSTEM_LOG_FILE, cumulative=False, custom_plugins=''):
        """
        System trace module

        """
        self.ROBOT_LIBRARY_LISTENER = self
        self._start_suite_name = ''
        self._modules = HostRegistryCache()
        try:
            level = BuiltIn().get_variable_value('${LOG LEVEL}')
            out_location = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except RobotNotRunningError:
            level = 'DEBUG'
            out_location = os.path.join(os.getcwd(), location)

        current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]

        with Logger as log:
            log.set_level('DEBUG' if level == 'TRACE' else level)
            rel_log_file_path = os.path.join(location, file_name)
            abs_log_file_path = os.path.join(out_location, location, file_name)
            log.set_log_destination(abs_log_file_path)
            logger.write(f'<a href="{rel_log_file_path}">{file_name}</a>', level='WARN', html=True)

        plugin_modules = load_modules(builtin_plugins, re.split(r'\s*,\s*', custom_plugins),
                                      base_path=current_dir, base_class=plugin_ssh_runner)
        db.PlugInService().update(**plugin_modules)

        db.DataHandlerService(os.path.normpath(os.path.join(out_location, location)), file_name, cumulative).start()
        super().__init__(db.DataHandlerService(), self._modules, location)
        plugins_table(db.PlugInService())

    def start_suite(self, suite: TestSuite, data):
        self._start_suite_name = suite.longname

    def end_suite(self, suite: TestSuite, result):
        if suite.longname == self._start_suite_name:
            self._modules.close_all()
            db.DataHandlerService().stop()
            logger.info(f"All system trace task closed by suite '{self._start_suite_name}' ending", also_console=True)

    @keyword("Create host connection")
    def create_host_connection(self, host, username, password, port=22, alias=None):
        """

        Create basic host connection module used for send plugin to

        :param host: IP address, DNS name
        :param username:
        :param password:
        :param port: 22 if omitted
        :param alias: 'username@host:port' if omitted
        :return: none
        """
        module = HostModule(db.PlugInService(), db.DataHandlerService().add_task, host, username, password, port, alias)
        module.start()
        _alias = self._modules.register(module)
        self._start_period(alias=module.alias)
        return module.alias

    @keyword("Close host connection")
    def close_host_connection(self, alias=None):
        """
        Close one connection
        :param alias: 'Current' used if omitted
        """
        self._stop_period(alias)
        self._modules.close(alias=alias)

    @keyword("Close all host connections")
    def close_all_host_connections(self):
        """
        Close all active connection modules with related plugin's
        """
        self._modules.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, **options):
        """
        Start plugin by its name on host queried by options keys
        :param plugin_name: name must be one for following in loaded table, column 'Class'
        | Alias              | Class               | Table
        |aTopPlugIn          | aTopPlugIn          |
        |                    |                     | atop_system_level

        :param options: 'Current' used if omitted
        """
        try:
            module: HostModule = self._modules.get_module(**options)
            assert plugin_name in db.PlugInService().keys(), \
                f"PlugIn '{plugin_name}' not registered"
            module.plugin_start(plugin_name, **options)
        except Exception as e:
            f, l = get_error_info()
            raise type(e)(f"{e}; File: {f}:{l}")

    @keyword("Stop trace plugin")
    def stop_trace_plugin(self, plugin_name, **options):
        module = self._modules.get_module(**options)
        module.plugin_terminate(plugin_name)

    @keyword("Start period")
    def start_period(self, period_name=None, **options):
        self._start_period(period_name, **options)

    def _start_period(self, period_name=None, **options):
        module: HostModule = self._modules.get_module(**options)
        db.DataHandlerService().execute(insert_sql(db.TableSchemaService().tables.Points.name,
                                                   db.TableSchemaService().tables.Points.columns),
                                        module.host_id, period_name or module.alias,
                                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        None)

    @keyword("Stop period")
    def stop_period(self, period_name=None, **options):
        self._stop_period(period_name, **options)

    def _stop_period(self, period_name=None, **options):
        module: HostModule = self._modules.get_module(**options)
        db.DataHandlerService().execute(update_sql(db.TableSchemaService().tables.Points.name, 'End',
                                                   HOST_REF=module.host_id, PointName=period_name or module.alias),
                                        datetime.now().strftime(DB_DATETIME_FORMAT))
