import os
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import is_truthy

from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.api.tools import Logger

from RemoteMonitorLibrary.library.listener import TraceListener
from RemoteMonitorLibrary.model.host_registry_model import HostRegistryCache, HostModule
from RemoteMonitorLibrary.utils import get_error_info
from RemoteMonitorLibrary.utils.sql_engine import insert_sql, update_sql, DB_DATETIME_FORMAT


class ConnectionKeywords(TraceListener):
    __doc__ = """=== Connections keywords ===
    `Create host monitor`
    
    `Close host monitor`
    
    `Close all host monitors`

    === PlugIn's keywords ===
    
    `Start monitor plugin`
    
    `Stop monitor plugin`
    
    === Mark points ===
    
    `Start period`
    
    `Stop period`
    
    `Set mark`"""

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
        test_start_kw = self._normalise_auto_mark(options.get('start_test', None), 'start_period')
        test_end_kw = self._normalise_auto_mark(options.get('end_test', None), 'stop_period')

        TraceListener.__init__(self, start_suite=suite_start_kw, end_suite=suite_end_kw,
                               start_test=test_start_kw, end_test=test_end_kw)
        # TraceListener.__init__(self)

    @staticmethod
    def _normalise_auto_mark(custom_kw, default_kw):
        if custom_kw is True:
            return default_kw
        elif custom_kw is not None:
            return custom_kw
        return None

    def get_keyword_names(self):
        return [
            self.create_host_monitor.__name__,
            self.close_host_monitor.__name__,
            self.close_all_host_monitors.__name__,
            self.start_monitor_plugin.__name__,
            self.stop_monitor_plugin.__name__,
            self.start_period.__name__,
            self.stop_period.__name__,
            self.set_mark.__name__
        ]

    @keyword("Create host monitor")
    def create_host_monitor(self, host, username, password, port=22, alias=None):
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
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   |       |                   | Default port; No alias |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   | 24    |                   | Custom port; No alias |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   | 24    |  ${my_name}       | Custom port; Alias    |
        |  Create host monitor   | 127.0.0.1 | any_user | any_password   |       |  alias=${my_name} | Default port; Alias    |

        """
        if not db.DataHandlerService().is_active:
            with Logger() as log:
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
        logger.info(f"Connection {module.alias} ready to be monitored")
        _alias = self._modules.register(module, module.alias)
        self._start_period(alias=module.alias)
        return module.alias

    @keyword("Close host monitor")
    def close_host_monitor(self, alias=None):
        """
        Stop all plugins related to host by its alias

        Arguments:
        - alias: 'Current' used if omitted
        """
        self._stop_period(alias)
        self._modules.stop_current()

    @keyword("Close all host monitors")
    def close_all_host_monitors(self):
        """
        Stop all active hosts plugins
        """
        self._modules.close_all()

    @keyword("Start monitor plugin")
    def start_monitor_plugin(self, plugin_name, alias=None, **options):
        """
        Start plugin by its name on host queried by options keys

        Arguments:
        - plugin_names: name must be one for following in loaded table, column 'Class'
        - alias: host monitor alias (Default: Current if omitted)
        - options: interval=... , persistent=yes/no,

        extra parameters relevant for particular plugin can be found in `BuiltIn plugins` section

        """
        try:
            monitor: HostModule = self._modules.get_connection(alias)
            assert plugin_name in db.PlugInService().keys(), \
                f"PlugIn '{plugin_name}' not registered"
            monitor.plugin_start(plugin_name, **options)
            logger.info(f"PlugIn '{plugin_name}' started on {monitor.alias}",
                        also_console=True)
        except Exception as e:
            f, li = get_error_info()
            raise type(e)(f"{e}; File: {f}:{li}")

    @keyword("Stop monitor plugin")
    def stop_monitor_plugin(self, plugin_name, alias=None, **options):
        monitor = HostRegistryCache().get_connection(alias)
        monitor.plugin_terminate(plugin_name, **options)
        logger.info(f"PlugIn '{plugin_name}' stopped on {monitor.alias}", also_console=True)

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

    @keyword("Set mark")
    def set_mark(self, mark_name, alias=None):
        module: HostModule = self._modules.get_connection(alias)
        db.DataHandlerService().execute(update_sql(db.TableSchemaService().tables.Points.name, 'Mark',
                                                   HOST_REF=module.host_id, PointName=mark_name),
                                        datetime.now().strftime(DB_DATETIME_FORMAT))