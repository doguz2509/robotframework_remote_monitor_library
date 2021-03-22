from abc import ABC

from system_trace.model import _ssh_execution_addon_abstract, _parser_addon_abstract, _data_handler_addon_abstract


class PlugIn(_ssh_execution_addon_abstract, _parser_addon_abstract, _data_handler_addon_abstract, ABC):
    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{self.name}")