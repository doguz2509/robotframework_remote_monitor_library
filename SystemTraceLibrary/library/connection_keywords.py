import os
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import is_truthy

from SystemTraceLibrary.api import db, Logger
from SystemTraceLibrary.library.listener import TraceListener
from SystemTraceLibrary.model.host_registry_model import HostRegistryCache, HostModule
from SystemTraceLibrary.utils import get_error_info
from SystemTraceLibrary.utils.sql_engine import insert_sql, update_sql, DB_DATETIME_FORMAT


class ConnectionKeywords(TraceListener):
    __doc__ = """=== Connections keywords ===
    `Create host connection`
    
    `Stop host trace`
    
    `Close host connection`
    
    `Close all host connections`

    === PlugIn's keywords ===
    
    `Start trace plugin`
    
    `Stop trace plugin`

    === Mark points ===
    
    `Start period`
    
    `Stop period`"""

    def __init__(self, rel_location, file_name, **options):
        """
        Initialise System Trace Library instance

        Arguments:
        - rel_location: relative log location
        - file_name: name for db & log files

        Optional parameters:
            - cumulative: delete existed db file if True, (Default: False)

        Auto keywords:
            - start_suite:
            - end_suite:
            - start_test:
            - end_test

        Keywords (start_period, stop_period will be assigned) will be assigned if True
        Provided keyword will be provided if defined

        Default - Nothing

        Note: working with current alias only
        """
        self._start_suite_name = ''
        self._modules = HostRegistryCache()
        self.location, self.file_name, self.cumulative = \
            rel_location, file_name, is_truthy(options.get('cumulative', False))

        suite_start_kw = self._normalise_auto_mark(options.get('start_suite', None), 'start_period')
        suite_end_kw = self._normalise_auto_mark(options.get('start_suite', None), 'stop_period')
        test_start_kw = self._normalise_auto_mark(options.get('start_test', True), 'start_period')
        test_end_kw = self._normalise_auto_mark(options.get('end_test', True), 'stop_period')

        TraceListener.__init__(self, start_suite=suite_start_kw, end_suite=suite_end_kw,
                               start_test=test_start_kw, end_test=test_end_kw)

    @staticmethod
    def _normalise_auto_mark(custom_kw, default_kw):
        if custom_kw is True:
            return default_kw
        elif custom_kw is not None:
            return custom_kw
        return None

    def get_keyword_names(self):
        return [
            self.create_host_connection.__name__,
            self.stop_host_trace.__name__,
            self.close_host_connection.__name__,
            self.close_all_host_connections.__name__,
            self.start_trace_plugin.__name__,
            self.stop_trace_plugin.__name__,
            self.start_period.__name__,
            self.stop_period.__name__
        ]

    @keyword("Create host connection")
    def create_host_connection(self, host, username, password, port=22, alias=None):
        """
        Create basic host connection module used for trace host
        Last created connection handled as 'current'
        In case tracing required for one host only, alias can be ignored

        Arguments:
        - host: IP address, DNS name, username, password:
        - port: 22 if omitted
        - alias: 'username@host:port' if omitted
        - str: alias

        Examples:
        |  KW                       |  Host     | Username | Password       | Port  | Alias             | Comments              |
        |  Create host connection   | 127.0.0.1 | any_user | any_password   |       |                   | Default port; No alias |
        |  Create host connection   | 127.0.0.1 | any_user | any_password   | 24    |                   | Custom port; No alias |
        |  Create host connection   | 127.0.0.1 | any_user | any_password   | 24    |  ${my_name}       | Custom port; Alias    |
        |  Create host connection   | 127.0.0.1 | any_user | any_password   |       |  alias=${my_name} | Default port; Alias    |

        """
        if not db.DataHandlerService().is_active:
            with Logger as log:
                level = BuiltIn().get_variable_value('${LOG LEVEL}')
                log.set_level('DEBUG' if level == 'TRACE' else level)
                output_location = BuiltIn().get_variable_value('${OUTPUT_DIR}')
                rel_log_file_path = os.path.join(self.location, self.file_name)
                abs_log_file_path = os.path.join(output_location, self.location, self.file_name)
                log.set_log_destination(abs_log_file_path)
                logger.write(f'<a href="{rel_log_file_path}">{self.file_name}</a>', level='WARN', html=True)
            db.DataHandlerService().init(os.path.join(output_location, self.location), self.file_name, self.cumulative)
            db.DataHandlerService().start()
        module = HostModule(db.PlugInService(), db.DataHandlerService().add_task, host, username, password, port, alias)
        module.start()
        _alias = self._modules.register(module, module.alias)
        self._start_period(alias=module.alias)
        return module.alias

    @keyword("Stop host trace")
    def stop_host_trace(self, alias=None):
        """
        Stop all plugins related to host by its alias

        Arguments:
        - alias: 'Current' used if omitted
        """
        self._stop_period(alias)
        self._modules.stop_current()

    @keyword("Close host connection")
    def close_host_connection(self, alias=None):
        """
        Stop all plugins activity on host

        Arguments:
        - alias: Connection host alias
        """
        self.stop_host_trace(alias)

    @keyword("Close all host connections")
    def close_all_host_connections(self):
        """
        Stop all active hosts plugins
        """
        self._modules.close_all()

    @keyword("Start trace plugin")
    def start_trace_plugin(self, plugin_name, alias=None, **options):
        """
        Start plugin by its name on host queried by options keys

        Arguments:
        - plugin_names: name must be one for following in loaded table, column 'Class'
        - alias: host module alias (Default: Current if omitted)
        - options: interval=... , persistent=yes/no

        | Alias              | Class               | Table  |
        | aTop          | aTop          |    |
        |                    |                     | atop_system_level |

        """
        try:
            module: HostModule = self._modules.get_connection(alias)
            assert plugin_name in db.PlugInService().keys(), \
                f"PlugIn '{plugin_name}' not registered"
            module.plugin_start(plugin_name, **options)
        except Exception as e:
            f, l = get_error_info()
            raise type(e)(f"{e}; File: {f}:{l}")

    @keyword("Stop trace plugin")
    def stop_trace_plugin(self, plugin_name, alias=None):
        module = HostRegistryCache().get_connection(alias)
        module.plugin_terminate(plugin_name)

    @keyword("Start period")
    def start_period(self, period_name=None, alias=None):
        self._start_period(period_name, alias)

    def _start_period(self, period_name=None, alias=None):
        module: HostModule = self._modules.get_connection(alias)
        db.DataHandlerService().execute(insert_sql(db.TableSchemaService().tables.Points.name,
                                                   db.TableSchemaService().tables.Points.columns),
                                        module.host_id, period_name or module.alias,
                                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        None)

    @keyword("Stop period")
    def stop_period(self, period_name=None, alias=None):
        self._stop_period(period_name, alias)

    def _stop_period(self, period_name=None, alias=None):
        module: HostModule = self._modules.get_connection(alias)
        db.DataHandlerService().execute(update_sql(db.TableSchemaService().tables.Points.name, 'End',
                                                   HOST_REF=module.host_id, PointName=period_name or module.alias),
                                        datetime.now().strftime(DB_DATETIME_FORMAT))
