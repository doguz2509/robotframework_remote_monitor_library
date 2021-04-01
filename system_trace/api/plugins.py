from abc import ABC

from system_trace.model.ssh_plugin_model import plugin_execution_abstract, Command, CommandsType


class PlugInAPI(ABC, plugin_execution_abstract):
    __doc__ = """Interactive command execution in main thread background
    Command starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


__all__ = ['PlugInAPI', 'Command', CommandsType]
