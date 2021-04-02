import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import library, keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.running import TestSuite

from system_trace.api import BgLogger
from system_trace.api.data_api import DataHandlerService, TableSchemaService, PlugInService
from system_trace.builtin_plugins.atop_plugin import aTopPlugIn
from system_trace.model.chart_model.html_template import HTML, HTML_IMAGE_REF
from system_trace.model.connection_module import ConnectionModule
from system_trace.model.connection_module_cache import ConnectionModuleCache
from system_trace.model.schema_model import DataUnit, SQL_ACTIONS
from system_trace.model.ssh_plugin_model import plugin_execution_abstract
from system_trace.utils import get_reader_class_from_module, show_plugins
from system_trace.utils.sql_engine import SQL_DB

DEFAULT_SYSTEM_TRACE_LOG = 'logs'

DEFAULT_SYSTEM_LOG_FILE = 'system_trace.log'


class _VisualisationLibrary:
    def __init__(self, db_obj, module_registry, rel_log_path, images='images'):
        try:
            self._output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except RobotNotRunningError:
            self._output_dir = os.getcwd()
        self._module_registry = module_registry
        self._log_path = rel_log_path
        self._images = images
        self._image_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, self._images))
        self._db: SQL_DB = db_obj

    @keyword("GenerateModuleStatistics")
    def generate_module_statistics(self, *marks, **module_filter):
        module: ConnectionModule = self._module_registry.get_module(**module_filter)
        # start = self._db.execute(TableFactory.MarkPoints.select_mark(start_mark))
        # start = None if start == [] else start[0][0]
        # end = self._db.execute(TableFactory.MarkPoints.select_mark(end_mark))
        # end = None if end == [] else end[0][0]
        #
        # marks = {n: t for n, t in self._db.execute(TableFactory.MarkPoints.get_marks(session))} if is_truthy(show_marks) else {}

        if not os.path.exists(self._image_path):
            os.mkdir(self._image_path)
        body = ''

        for alias, charts in {k: v.affiliated_charts() for k, v in module.active_plugins.items()}:
            for chart in charts:
                try:
                    sql_query = chart.compose_sql_query(session_name=alias)
                    for picture_name, file_path in chart.generate(self._db, self._image_path, sql_query, prefix=alias):
                        relative_image_path = os.path.relpath(file_path, os.path.normpath(
                            os.path.join(self._output_dir, self._log_path)))
                        body += HTML_IMAGE_REF.format(relative_path=relative_image_path, picture_title=picture_name)
                except Exception as e:
                    logger.error(f"Error: {e}")

        html_file_name = "{}.html".format(re.sub(r'\s+', '_', module.alias))
        html = HTML.format(title=module.alias, body=body)
        html_full_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, html_file_name))
        html_link_path = '/'.join([self._log_path, html_file_name])
        with open(html_full_path, 'w') as sw:
            sw.write(html)
        logger.warn(f"<a href=\"{html_link_path}\">Session '{module.alias}' statistics</a>", html=True)
        return f"<a href=\"{html_link_path}\">Session '{module.alias}' statistics</a>"


@library(scope='GLOBAL')
class SystemTraceLibrary(_VisualisationLibrary):
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, location='logs', file_name=DEFAULT_SYSTEM_LOG_FILE, cumulative=False, custom_plugins=None):
        """
        System trace module

        """
        self.ROBOT_LIBRARY_LISTENER = self
        self._start_suite_name = ''
        self._modules = ConnectionModuleCache()
        try:
            level = BuiltIn().get_variable_value('${LOG LEVEL}')
            out_location = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except RobotNotRunningError:
            level = 'DEBUG'
            out_location = os.path.join(os.getcwd(), location)

        current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]

        with BgLogger as log:
            log.set_level('DEBUG' if level == 'TRACE' else level)
            rel_log_file_path = os.path.join(location, file_name)
            abs_log_file_path = os.path.join(out_location, location, file_name)
            log.set_log_destination(abs_log_file_path)
            logger.write(f'<a href="{rel_log_file_path}">{file_name}</a>', level='WARN', html=True)

        custom_plugins_modules = {}
        if custom_plugins:
            for plugins_ in re.split(r'\s*,\s*', custom_plugins):
                custom_plugins_modules.update(get_reader_class_from_module(current_dir, plugins_,
                                                                           plugin_execution_abstract))
        if aTopPlugIn not in custom_plugins_modules.keys():
            custom_plugins_modules.update({'atop': aTopPlugIn})
        PlugInService().update(**custom_plugins_modules)

        for name, plugin in PlugInService().items():
            for table in plugin.affiliated_tables():
                TableSchemaService().register_table(table)
        DataHandlerService(os.path.join(out_location, location), file_name, cumulative).start()
        _VisualisationLibrary.__init__(self, DataHandlerService(), self._modules, location)
        show_plugins(PlugInService())

        self._plugin_threads = []

    def start_suite(self, suite: TestSuite, data):
        self._start_suite_name = suite.longname

    def end_suite(self, suite: TestSuite, result):
        if suite.longname == self._start_suite_name:
            self._modules.close_all()
            DataHandlerService().stop()
            logger.info(f"All system trace task closed by suite '{self._start_suite_name}' ending", also_console=True)

    @keyword("Create trace connection")
    def create_trace_connection(self, host, username, password, port=22, alias=None):
        module = ConnectionModule(PlugInService(), DataHandlerService().queue.put,
                                  host, username, password, port, alias)
        module.start()
        _alias = self._modules.register(module)
        self._start_period(module.alias)
        return module.alias

    @keyword("Close trace connection")
    def close_trace_connection(self, **kwargs):
        alias = self._modules.close(**kwargs)
        self._stop_period(alias)

    @keyword("Close all trace connections")
    def close_all_trace_connections(self):
        self._modules.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, **options):
        module: ConnectionModule = self._modules.get_module(**options)
        assert plugin_name in PlugInService().keys(), \
            f"PlugIn '{plugin_name}' not registered"
        module.plugin_start(plugin_name, **options)

    @keyword("Stop trace plugin")
    def stop_trace_plugin(self, plugin_name, **options):
        module = self._modules.get_module(**options)
        module.plugin_terminate(plugin_name)

    @keyword("Start period")
    def start_period(self, period_name):
        self._start_period(period_name)

    @staticmethod
    def _start_period(period_name):
        data = TableSchemaService().tables.Points.template(period_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                           None)
        DataHandlerService().queue.put(DataUnit(TableSchemaService().tables.Points, data))

    @keyword("Stop period")
    def stop_period(self, period_name):
        self._stop_period(period_name)

    @staticmethod
    def _stop_period(period_name):
        period_data = DataUnit(TableSchemaService().tables.Points, timeout=5,
                               sql=f"""SELECT * FROM Points ORDER BY Start DESC LIMIT 1""")
        DataHandlerService().queue.put(period_data)
        result = TableSchemaService().tables.Points.template(
            *list(period_data.result[0])[:2] + [datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        DataHandlerService().queue.put(DataUnit(TableSchemaService().tables.Points, result,
                                                sql_action=SQL_ACTIONS.UPDATE))
