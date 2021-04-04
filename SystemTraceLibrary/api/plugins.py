from abc import ABC

from SystemTraceLibrary.model.configuration import Configuration
from SystemTraceLibrary.model.runner_model.runner_abstracts import plugin_integration_abstract
from SystemTraceLibrary.model.runner_model.ssh_runner import plugin_ssh_runner
from SystemTraceLibrary.model.runner_model import Command, CommandsType
from SystemTraceLibrary.model.chart_model.chart_abstract import ChartAbstract


class PlugInAPI(ABC, plugin_ssh_runner, plugin_integration_abstract):
    __doc__ = """Interactive command execution in main thread background
    Command starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


__all__ = ['PlugInAPI',
           'CommandsType',
           Command.__name__,
           ChartAbstract.__name__,
           Configuration.__name__
           ]
