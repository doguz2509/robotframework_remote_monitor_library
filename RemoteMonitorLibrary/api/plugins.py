from abc import ABC

from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.model.runner_model.runner_abstracts import plugin_integration_abstract
from RemoteMonitorLibrary.model.runner_model.ssh_runner import SSHLibraryCommandScheduler
from RemoteMonitorLibrary.model.runner_model import Command, Parser, CommandSet_Type
from RemoteMonitorLibrary.model.chart_model.chart_abstract import ChartAbstract


class PlugInAPI(ABC, SSHLibraryCommandScheduler, plugin_integration_abstract):
    __doc__ = """Interactive command execution in main thread background
    Command starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


__all__ = ['PlugInAPI',
           'CommandSet_Type',
           Command.__name__,
           'CommandSet_Type',
           Parser.__name__,
           ChartAbstract.__name__,
           Configuration.__name__
           ]
