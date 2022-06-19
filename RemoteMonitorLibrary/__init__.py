import os

from RemoteMonitorLibrary.library import RemoteMonitorLibrary
from RemoteMonitorLibrary import utils
from RemoteMonitorLibrary import api
from RemoteMonitorLibrary import plugins_modules
from RemoteMonitorLibrary.version import VERSION

__author__ = 'Dmitry Oguz'
__author_email__ = 'doguz2509@gmail.com'
__version__ = VERSION
__url__ = 'https://github.com/doguz2509/robotframework_remote_monitor_library'
__package_name__ = os.path.split(os.path.split(__file__)[0])[1]


__all__ = [
    'api',
    'plugins_modules',
    'RemoteMonitorLibrary',
    '__author_email__',
    '__author__',
    '__version__',
    '__url__',
    '__package_name__'
]


