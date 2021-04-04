from abc import ABC
from typing import Iterable

from system_trace.model import schema_model as model
from system_trace.model.configuration import Configuration
from system_trace.model.ssh_plugin_model import plugin_execution_abstract, Command, CommandsType
from system_trace.model.chart_model.chart_abstract import ChartAbstract


class plugin_integration_abstract(object):
    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{id(self)}")

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return []

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return []


class PlugInAPI(ABC, plugin_execution_abstract, plugin_integration_abstract):
    __doc__ = """Interactive command execution in main thread background
    Command starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


__all__ = ['PlugInAPI',
           'Command',
           CommandsType,
           ChartAbstract.__name__,
           'Configuration'
           ]
