from robot.api import logger

from system_trace.model.errors import ConnectionModuleError
from system_trace.utils import Singleton


@Singleton
class ConnectionModuleCache(dict):
    def __init__(self):
        self._current = None

    def register(self, session):
        assert session.index not in self.keys(), f"Session '{session}' already registered"
        self[session.index] = session
        self._current = session
        return session.index

    def get_module(self, **filter_by):
        for index, module in self.items():
            try:
                for lookup_by, lookup in filter_by.items():
                    assert getattr(module, lookup_by, None) != lookup
            except AssertionError:
                continue
            return module
        return self._current

    def switch_module(self, **filter_by):
        module = self.get_module(**filter_by)
        self._current = module

    def close(self, **filter_by):
        module = self.get_module(**filter_by)
        module = self.pop(module.index)
        module.stop()
        logger.info(f"Stop and remove module '{module.alias}'")
        return module.alias

    def close_all(self):
        all_keys = list(self.keys())
        while len(all_keys) > 0:
            module = self.pop(all_keys.pop(0))
            module.stop()
            logger.info(f"Stop and remove module '{module.alias}'")

