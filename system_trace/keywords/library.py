import os

from robot.api.deco import library, keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import is_truthy

from system_trace.utils.bg_logger import Logger
from system_trace.utils.configuration import Configuration


class _Tracer:
    pass

    @keyword("Create connection")
    def create_connection(self, host, username, password, port=22, alias=None):
        pass

    @keyword("Close connection")
    def close_connection(self, alias=None):
        pass

    @keyword("Close all connections")
    def close_all_connections(self):
        pass

    @keyword("Add interactive command")
    def add_interactive_command(self, command, alias=None, interval=None):
        pass

    @keyword("Add interactive command")
    def add_periodical_command(self, command, alias=None, interval=None):
        pass

    @keyword("Start plugin")
    def start_plugin(self, plugin_name, alias=None):
        pass

    @keyword("Stop plugin")
    def stop_plugin(self, plugin_name, alias=None):
        pass


class _CheckPoints:
    @keyword("Start period")
    def start_period(self, period_name, alias=None):
        pass

    @keyword("Stop period")
    def stop_period(self, period_name, alias=None):
        pass


class _Visualisation:
    @keyword("Generate chart")
    def generate_chart(self, alias=None, period_name=None):
        pass


@library(scope='GLOBAL')
class BackgroundSystemTrace(_Tracer, _Visualisation):
    def __init__(self, out_dir='logs', **credentials):
        """
        System data trace module

        :param credentials: host, username, password, port[22]
        """
        log_file = credentials.pop('file') if 'file' in credentials else None
        log_file = log_file or self.__class__.__name__
        if 'sudo' in credentials.keys():
            credentials.update({'sudo': is_truthy(credentials.get('sudo'))})

        self._conf = Configuration(**credentials)
        self._credentials = {'sudo': self._conf.pop('sudo', 'no'),
                             'sudo_password': self._conf.pop('sudo_password', None)}
        self._log_dir = out_dir
        self._threads: dict = {}
        self._event: Event = None
        self._queue: threadsafe.tsQueue = None

        self._session_name_cache = []

        init_db_schema()

        with Logger() as log:
            level = BuiltIn().get_variable_value('${LOG LEVEL}')
            log.set_level('DEBUG' if level == 'TRACE' else level)
            out_location = BuiltIn().get_variable_value('${OUTPUT_DIR}')
            rel_log_file_path = os.path.join(out_dir, log_file)
            abs_log_file_path = os.path.join(out_location, out_dir, log_file)
            log.set_log_destination(abs_log_file_path)
            logger.info(f"System trace log redirected to file: {rel_log_file_path}", also_console=True)
            logger.write(f'<a href="{rel_log_file_path}">{log_file}</a>', level='WARN', html=True)
            _path = os.path.join(BuiltIn().get_variable_value('${OUTPUT_DIR}'), self._log_dir)
            self._db = SQLDataHandler(_path, logger=log)
        Visualisation.__init__(self, self._db, out_dir)

    @property
    def is_active(self):
        return len(self._threads) > 0

    def _generate_unic_handle(self, session_alias=None):
        if session_alias is None:
            try:
                session_alias = BuiltIn().get_variable_value('${TEST NAME}')
            except Exception as e:
                session_alias = BuiltIn().get_variable_value('${SUITE NAME}')
        if session_alias in self._session_name_cache:
            session_alias = \
                f"{session_alias}_{len([s for s in self._session_name_cache if s.startwith(session_alias)]):02d}"

        self._session_name_cache.append(session_alias)
        return session_alias

    @keyword("StartSystemTrace")
    def start_system_trace(self, interval, session_alias=None, duration=None):
        """
        Start syStem trace keyword
        Starting background data collection (netstat, lsof, top) from preconfigured host

        :param session_alias: Session name, auto set test or suite name if omitted
        :param duration: Overall measurement duration
        :param interval: Measurement interval
        """

        assert not self.is_active, "Trace process with already being running"
        interval_in_sec = timestr_to_secs(interval)

        session_alias = self._generate_unic_handle(session_alias)

        try:
            self._event = Event()
            self._queue = threadsafe.tsQueue()
            self._db.start(session_alias, interval_in_sec, self._event, self._queue)
            self._threads.update({'data_handler': self._db})
            tracer = trace_runner(interval_in_sec, self._event,
                                  SystemDataCollectRunner(self._conf, **self._credentials),
                                  logger=Logger(),
                                  queue=self._queue)
            tracer.start()
            # tracer.run()
            self._threads.update({'tracer': tracer})

            if duration:
                duration_in_sec = timestr_to_secs(duration)
                timer = Timer(duration_in_sec, self.stop_system_trace, [f"Duration {duration} expired"])
                timer.start()
                self._threads.update({'timer': timer})
            else:
                logger.info(f"System tracing start forever")
            return session_alias
        except Exception as e:
            Logger().error(f"{e}")
            self.stop_system_trace(f"Error occurred: {e}")
            raise

    @keyword("Add periodical command")
    def add_periodical_command(self, command, alias=None, expected_rc=None, expected_stdout=None, order=-1,
                               store_to_var=None, **permissions):
        assert self.is_active, "System tracing not active"
        if expected_rc is not None:
            expected_rc = int(expected_rc)
        if order != -1:
            order = int(order)

        command_wrapper = CustomPeriodicalCommandRunner(Configuration(**self._conf),
                                                        command=command, alias=alias,
                                                        expected_rc=expected_rc,
                                                        expected_stdout=expected_stdout,
                                                        **permissions)

        self._threads['tracer'].add_connector(command_wrapper, order=order)
        if store_to_var:
            BuiltIn().set_global_variable(store_to_var, command_wrapper.name)
        return command_wrapper.name

    @keyword("Remove periodical command")
    def remove_periodical_command(self, alias):
        assert self.is_active, "System tracing not active"
        self._threads['tracer'].remove_connector(alias)

    @keyword("Add background command")
    def add_background_command(self, command, alias=None, collect_interval='5s',
                               expected_pattern=None, unexpected_pattern=None):
        command_thread = CustomBackgroundCommandRunner(command, self._conf, alias, collect_interval,
                                                       expected_pattern=expected_pattern,
                                                       unexpected_pattern=unexpected_pattern,
                                                       queue=self._queue, event=self._event, logger=Logger())
        command_thread.start()
        self._threads[command_thread.alias] = command_thread

        return command_thread.alias

    @keyword("Remove background command")
    def remove_background_command(self, alias):
        try:
            command_thread = self._threads.pop(alias)
            command_thread.join()
            logger.info(f"command '{command_thread.command}' stopped after {command_thread.execution_counter} iterations")
        except KeyError:
            logger.error(f"No thread for alias '{alias}' found")

    def _get_last_ts_id(self):
        last_session_id = self._db.execute(TableFactory.Sessions.get_last_session)
        logger.debug(f"Last session occurred: {last_session_id}")
        while isinstance(last_session_id, (tuple, list)):
            last_session_id = last_session_id[0]

        last_ts = self._db.execute(TableFactory.TimeReference.get_last_entry(last_session_id))
        if len(last_ts) > 0:
            logger.debug(f"Last session time stamp occurred: {last_ts}")
            while isinstance(last_ts, (tuple, list)):
                last_ts = last_ts[0]
        else:
            self._db.execute(TableFactory.TimeReference.insert_sql, last_session_id, None, datetime.now())
            last_ts = self._db.execute(TableFactory.TimeReference.get_last_entry(last_session_id))
            while isinstance(last_ts, (tuple, list)):
                last_ts = last_ts[0]
            logger.debug(f"Time stamps not found; Create new {last_ts}")
        return last_ts

    @keyword("Add marking tag")
    def add_marking_tag(self, title):
        """
        Adding mark during system tracing
        :param title: Tag name
        """
        try:
            last_ts = self._get_last_ts_id()
            self._db.execute(TableFactory.MarkPoints.insert_sql, last_ts, title)
            logger.info(f"Tag '{title}' added")
        except Exception as e:
            raise RuntimeError(f"Unexpected error occurred: {e}")

    @keyword("StopSystemTrace")
    def stop_system_trace(self, reason=None):
        try:
            assert self.is_active
            logger.info("System tracing stop invoked{}".format(f" by {reason}" if reason else ''))
            if self._event:
                self._event.set()
            for name, th in self._threads.items():
                if isinstance(th, Timer):
                    th.cancel()
                else:
                    th.join()
                logger.debug(f"Task {name} stopped")

            self._threads = {}
            self._db.execute(
                f'UPDATE Sessions set End = "{datetime.now()}" WHERE SESSION_ID=(SELECT max(SESSION_ID) FROM Sessions)'
            )

        except AssertionError:
            logger.warn("System tracing not active")
        except Exception as e:
            logger.warn(f"Unexpected error occurred: {e}")
