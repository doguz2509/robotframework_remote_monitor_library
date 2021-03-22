from threading import RLock
from time import sleep
from typing import Any

from . import Logger


class Empty(Exception):
    pass


class tsQueue:
    def __init__(self, get_limit=10):
        self._get_limit = get_limit
        self._queue = []
        self._lock = RLock()

    def put(self, item):
        with self._lock:
            self._queue.append(item)
            Logger().debug(f"Put item ({len(self._queue)})")

    def _get(self) -> Any:
        try:
            self._lock.acquire()
            if len(self) == 0:
                return Empty()
            return self._queue.pop(0)
            # Logger().debug(f"Get item ({len(self._queue)})")
        finally:
            self._lock.release()

    def get(self, get_count=None) -> list:
        count = 0
        limit = get_count or self._get_limit
        while count <= limit:
            count += 1
            yield self._get()
            sleep(0.1)

    def __len__(self):
        return len(self._queue)

    qsize = __len__

    def empty(self):
        return len(self) == 0

