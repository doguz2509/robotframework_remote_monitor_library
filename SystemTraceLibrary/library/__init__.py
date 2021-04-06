from robot.api.deco import library

from SystemTraceLibrary.version import VERSION
from SystemTraceLibrary.library.base_keywords import base_keywords


@library(scope='GLOBAL', doc_format='reST')
class SystemTraceLibrary(base_keywords):
    ROBOT_LIBRARY_VERSION = VERSION

    # TODO: Add library documentation
    __doc__ = """Trace System or any other data on linux hosts
    == Library Keywords ==
    === Connections management===
    `Create host connection`
    `Close host connection`
    `Close all host connections`
    
    === PlugIn's management ===
    `Start trace plugin`
    `Stop trace plugin`
    
    === Mark points ===
    `Start period`
    `Stop period`
    
    === Statistics, measurement, analise ===
    `GenerateModuleStatistics`
    `Evaluate statistic trend` - TBD
    """
