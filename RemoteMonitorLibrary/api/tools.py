from ..utils import Singleton
from ..utils.collections import CacheList


@Singleton
class GlobalErrors(list):
    pass


__all__ = [
    'CacheList',
    'GlobalErrors'
]
