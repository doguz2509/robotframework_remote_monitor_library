from typing import List

from ..model.errors import RunnerError
from ..utils import Singleton
from ..utils.collections import CacheList


@Singleton
class GlobalErrors(list, List[RunnerError]):
    pass


__all__ = [
    'CacheList',
    'GlobalErrors'
]
