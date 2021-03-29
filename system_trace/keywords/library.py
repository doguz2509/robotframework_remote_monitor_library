import os

from robot.api import logger
from robot.api.deco import library, keyword
from robot.libraries.BuiltIn import BuiltIn

from system_trace.api import BgLogger
from system_trace.api import DataHandlerService
from system_trace.keywords.trace_connection_cache import TraceConnectionCache
from system_trace.model.robot_data_reader import _get_reader_class_from_path, _get_reader_class_from_module
from system_trace.model.schema_model import DbSchema
from system_trace.model.session_model import TraceSession
from system_trace.model.ssh_addon import plugin_execution_abstract
from system_trace.system_plugins.atop_plugin import aTopPlugIn

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
        return _get_reader_class_from_module(path, plugin_module_name, plugin_execution_abstract)
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
        self._plugin_registry = dict(atop=aTopPlugIn, **_verify_addon_plugins(**custom_plugins))

        self._plugin_threads = []
        for name, plugin in self._plugin_registry.items():
            for table in plugin().affiliated_tables:
                DbSchema().register_table(table)
        DataHandlerService(os.path.join(out_location, location), file_name, cumulative).start()

    def end_suite(self, data, suite):
        self._sessions.close_all()
        DataHandlerService.stop()
        BgLogger.info(f"All system trace task closed by last Suite ending")

    @keyword("Create connection")
    def create_connection(self, host, username, password, port=22, alias=None):
        session = TraceSession(host, username, password, port, alias, *self._sessions.name_cache)
        session.start()
        self._sessions.register(session, alias)

    @keyword("Close connection")
    def close_connection(self, alias=None):
        current_session = self._sessions.get_connection()
        try:
            self._sessions.switch(alias)
            self._sessions.close_current()
        finally:
            self._sessions.switch(current_session)

    @keyword("Close all connections")
    def close_all_connections(self):
        self._sessions.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, alias=None, *args, **kwargs):
        session: TraceSession = self._sessions.get_connection(alias)
        assert plugin_name in self._plugin_registry.keys(), f"PlugIn '{plugin_name}' not registered"
        plugin_obj = self._plugin_registry.get(plugin_name, *args, session_id=session.session_id, **kwargs)

    @keyword("Stop trace plugin")
    def stop_trace_plugin(self, plugin_name, alias=None):
        session = self._sessions.get_connection(alias)
        session.stop(plugin_name)

    @keyword("Start period")
    def start_period(self, period_name, alias=None):
        session: TraceSession = self._sessions.get_connection(alias)
        DataHandlerService().execute(DataHandlerService().tables.MarkPoints.insert_sql,
                                     DataHandlerService().last_time_tick, session.session_id, 'Start', period_name)

    @keyword("Stop period")
    def stop_period(self, period_name, alias=None):
        session: TraceSession = self._sessions.get_connection(alias)
        DataHandlerService().execute(DataHandlerService().tables.MarkPoints.insert_sql,
                                     DataHandlerService().last_time_tick, session.session_id, 'Stop', period_name)
