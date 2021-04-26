from threading import RLock
from typing import Any

from RemoteMonitorLibrary.utils import Logger


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
            Logger().debug(f"Item '{id(item)}' enqueued")

    def get(self) -> Any:
        with self._lock:
            try:
                Logger().debug(f"Item '{id(self._queue[0])}' dequeued")
                yield self._queue.pop(0)
            except IndexError:
                yield Empty()

    def __len__(self):
        return len(self._queue)

    qsize = __len__

    def empty(self):
        return len(self) == 0


class CacheList(list):
    def __init__(self, max_size=50):
        list.__init__(self)
        self._max_size = max_size

    def append(self, item) -> None:
        while len(self) >= self._max_size:
            self.pop(0)
        super().append(item)
