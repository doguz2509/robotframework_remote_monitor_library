from threading import RLock
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

    def get(self) -> Any:
        with self._lock:
            try:
                yield self._queue.pop(0)
            except IndexError:
                yield Empty()

    # def get(self, get_count=None) -> list:
    #     count = 0
    #     limit = get_count or self._get_limit
    #     while count <= limit:
    #         count += 1
    #         yield self._get()
    #         sleep(0.01)

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
