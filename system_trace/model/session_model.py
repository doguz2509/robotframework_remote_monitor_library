from threading import Event

from robot.libraries.BuiltIn import BuiltIn

import system_trace.model.schema_model
from system_trace.api import DataHandlerService
from system_trace.model.configuration import Configuration


def _generate_unique_handle(session_alias=None, *cache):
    if session_alias is None:
        try:
            session_alias = BuiltIn().get_variable_value('${TEST NAME}')
        except Exception as e:
            session_alias = BuiltIn().get_variable_value('${SUITE NAME}')
    if session_alias in cache:
        session_alias = f"{session_alias}_{len([s for s in cache if s.startwith(session_alias)]):02d}"

    return session_alias


class TraceSession:
    def __init__(self, host, username, password,
                 port=None, alias=None, interval=None,
                 certificate=None,
                 run_as_sudo=False,
                 *cache):
        self._name = _generate_unique_handle(alias, *cache)
        self._configuration = Configuration(host=host, username=username, password=password,
                                            port=port, certificate=certificate, run_as_sudo=run_as_sudo,
                                            interval=interval)
        self._session_id = None
        self._session_event: Event = None

    @property
    def name(self):
        return self._name

    @property
    def configuration(self):
        return self._configuration

    @property
    def session_id(self):
        return self._session_id

    @property
    def event(self):
        return self._session_event

    def start(self):
        DataHandlerService.execute(system_trace.model.schema_model.Sessions.insert_sql,
                                   None, 'CURRENT_TIMESTAMP', None, self.session_id)
        self._session_event = Event()

    def close(self):
        assert self._session_event, f"Session '{self.name}' not started yet"
        self._session_event.set()
        DataHandlerService.execute(
            f'UPDATE Sessions set End = CURRENT_TIMESTAMP '
            f'WHERE SESSION_ID=(SELECT SESSION_ID FROM Sessions WHERE Title = "{self.session_id}")'
        )
