import os

from robot.api import logger
from robot.api.deco import library, keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.running import TestSuite
from robot.utils import DotDict

from system_trace.api import BgLogger
from system_trace.api.data_api import DataHandlerService, TableSchemaService, PlugInService
from system_trace.builtin_plugins.atop_plugin import aTopPlugIn
from system_trace.model.connection_cache_model import TraceConnectionCache
from system_trace.model.schema_model import DataUnit
from system_trace.model.session_model import TraceSession
from system_trace.model.ssh_plugin_model import plugin_execution_abstract
from system_trace.utils import get_reader_class_from_module

DEFAULT_SYSTEM_TRACE_LOG = 'logs'

DEFAULT_SYSTEM_LOG_FILE = 'system_trace.log'


class _Visualisation:
    @keyword("Generate chart")
    def generate_chart(self, alias=None, period_name=None):
        pass


def _verify_addon_plugins(**plugins):
    err = []
    for name, plugin in plugins.items():
        try:
            assert issubclass(plugin, plugin_execution_abstract), \
                f"Class type for '{name}' must be typeof(plugin_execution_abstract) vs. {plugin_execution_abstract}"
        except AssertionError as e:
            err.append(e)
    assert len(err) == 0, f"Some of plugins have wrong definition"
    return plugins


def _load_plugins(path, plugin_module_name=None):
    if plugin_module_name:
        return get_reader_class_from_module(path, plugin_module_name, plugin_execution_abstract)
    return {}


@library(scope='GLOBAL')
class SystemTraceLibrary(_Visualisation):
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, location='logs', file_name=DEFAULT_SYSTEM_LOG_FILE, cumulative=False, custom_plugins=None):
        """
        System data trace module

        :param credentials: host, username, password, port[22]
        """

        self.ROBOT_LIBRARY_LISTENER = self
        self._start_suite_name = ''
        self._sessions = TraceConnectionCache()
        try:
            level = BuiltIn().get_variable_value('${LOG LEVEL}')
        except Exception:
            level = 'DEBUG'
        try:
            out_location = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except Exception:
            out_location = os.path.join(os.getcwd(), location)

        current_dir = os.path.split(BuiltIn().get_variable_value('${SUITE SOURCE}'))[0]

        with BgLogger as log:
            log.set_level('DEBUG' if level == 'TRACE' else level)
            rel_log_file_path = os.path.join(location, file_name)
            abs_log_file_path = os.path.join(out_location, location, file_name)
            log.set_log_destination(abs_log_file_path)
            logger.write(f'<a href="{rel_log_file_path}">{file_name}</a>', level='WARN', html=True)

        custom_plugins = _load_plugins(current_dir, custom_plugins)
        if aTopPlugIn not in custom_plugins.keys():
            custom_plugins.update({'atop': aTopPlugIn})
        PlugInService().update(**custom_plugins)

        for name, plugin in PlugInService().items():
            for table in plugin().affiliated_tables:
                TableSchemaService().register_table(table)
        DataHandlerService(os.path.join(out_location, location), file_name, cumulative).start()

        show_obj = DotDict(Alias='Class')
        show_obj.update(**{k: v.__name__ for k, v in PlugInService().items()})
        logger.info("Following plugins registered:\n\t{}".format(
            '\n\t'.join([f"{k:20s}: {v}" for k, v in show_obj.items()])), also_console=True)

        self._plugin_threads = []

    def start_suite(self, suite: TestSuite, data):
        self._start_suite_name = suite.longname

    def end_suite(self, suite: TestSuite, result):
        if suite.longname == self._start_suite_name:
            self._sessions.close_all()
            DataHandlerService().stop()
            logger.info(f"All system trace task closed by suite '{self._start_suite_name}' ending", also_console=True)

    @keyword("Create trace connection")
    def create_trace_connection(self, host, username, password, port=22, alias=None):
        session = TraceSession(PlugInService(), DataHandlerService().queue.put, host, username, password, port, alias)
        assert session not in self._sessions.connections
        session.start()
        self._sessions.register(session, session.id)
        self._start_period(f"Session trace {session.id}")

    @keyword("Close trace connection")
    def close_trace_connection(self, alias=None):
        current_session = self._sessions.get_connection()
        session_to_close_id = ''
        try:
            self._sessions.switch(alias)
            session_to_close_id = self._sessions.get_connection().id
            self._sessions.close_current()
            self._stop_period(f"Session trace {session_to_close_id}")
        finally:
            if current_session.config.alias != session_to_close_id:
                self._sessions.switch(current_session)

    @keyword("Close all trace connections")
    def close_all_trace_connections(self):
        self._sessions.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, alias=None, interval=None):
        session: TraceSession = self._sessions.get_connection(alias)
        assert plugin_name in PlugInService().keys(), f"PlugIn '{plugin_name}' not registered"
        session.plugin_start(plugin_name, interval)

    @keyword("Stop trace plugin")
    def stop_trace_plugin(self, plugin_name, alias=None):
        session = self._sessions.get_connection(alias)
        session.plugin_terminate(plugin_name)

    @keyword("Start period")
    def start_period(self, period_name):
        self._start_period(period_name)

    @staticmethod
    def _start_period(period_name):
        data = TableSchemaService().tables.Points.template(None, 'Start', period_name)
        DataHandlerService().queue.put(DataUnit(TableSchemaService().tables.Points, data))

    @keyword("Stop period")
    def stop_period(self, period_name):
        self._stop_period(period_name)

    @staticmethod
    def _stop_period(period_name):
        data = TableSchemaService().tables.Points.template(None, 'Stop', period_name)
        DataHandlerService().queue.put(DataUnit(TableSchemaService().tables.Points, data))
