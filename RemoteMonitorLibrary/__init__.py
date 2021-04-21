import os

from RemoteMonitorLibrary.library import RemoteMonitorLibrary
from RemoteMonitorLibrary import utils
from RemoteMonitorLibrary import api
from RemoteMonitorLibrary import plugins
from RemoteMonitorLibrary.version import VERSION

__author__ = 'Dmitry Oguz'
__author_email__ = 'doguz2509@gmail.com'
__version__ = VERSION
__url__ = 'https://github.com/doguz2509/robotframework_system_trace_library'
__package_name__ = os.path.split(os.path.split(__file__)[0])[1]


__all__ = [
    'api',
    'builtin_plugins',
    'RemoteMonitorLibrary',
    '__author_email__',
    '__author__',
    '__version__',
    '__url__',
    '__package_name__'
]


