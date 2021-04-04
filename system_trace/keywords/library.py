import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import library, keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.running import TestSuite

from system_trace import builtin_plugins
from system_trace.api import Logger, db, host_registry
from system_trace.api.db import TableSchemaService
from system_trace.model.chart_model.html_template import HTML, HTML_IMAGE_REF
from system_trace.model.runner_model.ssh_runner import plugin_ssh_runner
from system_trace.utils import show_plugins, get_error_info
from system_trace.utils.load_modules import load_modules
from system_trace.utils.sql_engine import insert_sql, update_sql, DB_DATETIME_FORMAT

DEFAULT_SYSTEM_TRACE_LOG = 'logs'

DEFAULT_SYSTEM_LOG_FILE = 'system_trace.log'


class _data_view_and_analyse:
    def __init__(self, db_obj, module_registry, rel_log_path, images='images'):
        try:
            self._output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except RobotNotRunningError:
            self._output_dir = os.getcwd()
        self._module_registry = module_registry
        self._log_path = rel_log_path
        self._images = images
        self._image_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, self._images))
        self._db: db.DataHandlerService = db_obj

    def _get_period_marks(self, period, module_id):
        start = self._db.execute(TableSchemaService().tables.Points.queries.select_state('Start', module_id, period))
        start = None if start == [] else start[0][0]
        end = self._db.execute(TableSchemaService().tables.Points.queries.select_state('End', module_id, period))
        end = datetime.now().strftime(DB_DATETIME_FORMAT) if end == [] else end[0][0]
        return dict(start_mark=start, end_mark=end)

    @keyword("GenerateModuleStatistics")
    def generate_module_statistics(self, period=None, **module_filter):
        module: host_registry.HostModule = self._module_registry.get_module(**module_filter)
        marks = self._get_period_marks(period, module.host_id) if period else {}

        if not os.path.exists(self._image_path):
            os.mkdir(self._image_path)
        body = ''

        for alias, plugin in {k: v for k, v in module.active_plugins.items()}.items():
            for chart in plugin.affiliated_charts():
                try:
                    sql_query = chart.compose_sql_query(host_name=plugin.name, **marks)
                    logger.debug(f"{plugin.type}{f'_{period}' if period else ''}_{marks}\n{sql_query}")
                    for picture_name, file_path in chart.generate(self._db,
                                                                  self._image_path,
                                                                  sql_query,
                                                              prefix=f"{plugin.type}{f'_{period}' if period else ''}"):
                        relative_image_path = os.path.relpath(file_path, os.path.normpath(
                            os.path.join(self._output_dir, self._log_path)))
                        body += HTML_IMAGE_REF.format(relative_path=relative_image_path, picture_title=picture_name)
                except Exception as e:
                    logger.error(f"Error: {e}")

        html_file_name = "{}.html".format(re.sub(r'\s+', '_', period or module.alias))
        html = HTML.format(title=period or module.alias, body=body)
        html_full_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, html_file_name))
        html_link_path = '/'.join([self._log_path, html_file_name])
        with open(html_full_path, 'w') as sw:
            sw.write(html)
        logger.warn(f"<a href=\"{html_link_path}\">Session '{period or module.alias}' statistics</a>", html=True)
        return f"<a href=\"{html_link_path}\">Session '{period or module.alias}' statistics</a>"


@library(scope='GLOBAL')
class SystemTraceLibrary(_data_view_and_analyse):
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, location='logs', file_name=DEFAULT_SYSTEM_LOG_FILE, cumulative=False, custom_plugins=None):
        """
        System trace module

        """
        self.ROBOT_LIBRARY_LISTENER = self
        self._start_suite_name = ''
        self._modules = host_registry.HostRegistryCache()
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

        # custom_plugins_modules = {}
        # if custom_plugins:
        #     for plugins_ in re.split(r'\s*,\s*', custom_plugins):
        #         custom_plugins_modules.update(load_classes_from_module_by_name(current_dir, plugins_,
        #                                                                        plugin_ssh_runner))
        # for buildin_module in get_class_from_module(builtin_plugins):
        #     if buildin_module not in custom_plugins_modules.keys():
        #         custom_plugins_modules.update({'atop': buildin_module})
        plugin_modules = load_modules(builtin_plugins, custom_plugins,
                                      base_path=current_dir, base_class=plugin_ssh_runner)
        db.PlugInService().update(**plugin_modules)

        db.DataHandlerService(os.path.join(out_location, location), file_name, cumulative).start()
        _data_view_and_analyse.__init__(self, db.DataHandlerService(), self._modules, location)
        show_plugins(db.PlugInService())

        self._plugin_threads = []

    def start_suite(self, suite: TestSuite, data):
        self._start_suite_name = suite.longname

    def end_suite(self, suite: TestSuite, result):
        if suite.longname == self._start_suite_name:
            self._modules.close_all()
            db.DataHandlerService().stop()
            logger.info(f"All system trace task closed by suite '{self._start_suite_name}' ending", also_console=True)

    @keyword("Create host connection")
    def create_host_connection(self, host, username, password, port=22, alias=None):
        module = host_registry.HostModule(db.PlugInService(), db.DataHandlerService().add_task,
                                          host, username, password, port, alias)
        module.start()
        _alias = self._modules.register(module)
        self._start_period(alias=module.alias)
        return module.alias

    @keyword("Close host connection")
    def close_host_connection(self, alias=None):
        self._stop_period(alias)
        self._modules.close(alias=alias)

    @keyword("Close all host connections")
    def close_all_host_connections(self):
        self._modules.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, **options):
        try:
            module: host_registry.HostModule = self._modules.get_module(**options)
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
        module: host_registry.HostModule = self._modules.get_module(**options)
        db.DataHandlerService().execute(insert_sql(db.TableSchemaService().tables.Points.name,
                                                   db.TableSchemaService().tables.Points.columns),
                                        module.host_id, period_name or module.alias,
                                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        None)

    @keyword("Stop period")
    def stop_period(self, period_name=None, **options):
        self._stop_period(period_name, **options)

    def _stop_period(self, period_name=None, **options):
        module: host_registry.HostModule = self._modules.get_module(**options)
        # period_data = db.DataHandlerService().execute(select_sql(db.TableSchemaService().tables.Points.name, '*',
        #                                                          HOST_REF=module.host_id,
        #                                                          PointName=period_name or module.alias))[0]
        #
        # updated_period_data = list(period_data)[:3] + [datetime.now().strftime(DB_DATETIME_FORMAT)]

        db.DataHandlerService().execute(update_sql(db.TableSchemaService().tables.Points.name, 'End',
                                                   HOST_REF=module.host_id, PointName=period_name or module.alias),
                                        datetime.now().strftime(DB_DATETIME_FORMAT))
