from ..model.errors import PlugInError
from ..utils import Singleton
from ..utils.collections import CacheList, tsQueue
from ..utils.bg_logger import Logger


@Singleton
class GlobalErrors(list):
    pass


__all__ = [
    'CacheList',
    'Logger',
    'GlobalErrors'
]
