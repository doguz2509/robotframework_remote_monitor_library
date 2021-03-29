from system_trace.model import schema_model as model
from .plugin import NonInteractivePlugIn, InteractivePlugIn

from ..model.db_service import DataHandler
from ..utils import Logger, Singleton

BgLogger = Logger()


@Singleton
class DataHandlerService(DataHandler):
    pass


__all__ = [
    'NonInteractivePlugIn',
    'InteractivePlugIn',
    'BgLogger',
    'model',
    'DataHandlerService'
]
