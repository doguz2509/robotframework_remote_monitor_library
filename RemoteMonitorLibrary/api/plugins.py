from abc import ABC

from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.model.runner_model import Parser, plugin_integration_abstract
from RemoteMonitorLibrary.model.chart_abstract import ChartAbstract
from RemoteMonitorLibrary.runner.ssh_runner import SSHLibraryPlugInWrapper, SSHLibraryCommand


class PlugInAPI(ABC, SSHLibraryPlugInWrapper, plugin_integration_abstract):
    __doc__ = """SSHLibraryCommand execution in background thread
    SSHLibraryCommand starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


__all__ = ['PlugInAPI',
           SSHLibraryCommand.__name__,
           Parser.__name__,
           ChartAbstract.__name__,
           Configuration.__name__
           ]