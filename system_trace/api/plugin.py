from abc import ABC

from system_trace.model.ssh_addon import ssh_non_interactive_plugin, ssh_interactive_plugin


class InteractivePlugIn(ABC, ssh_interactive_plugin):
    __doc__ = """Interactive command execution in main thread background
    Command starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """
    pass


class NonInteractivePlugIn(ABC, ssh_non_interactive_plugin):
    __doc__ = """Command being executing each time interval;
    Output collecting during execution and sending to parsing and loading to data handler
    """
    pass


__all__ = [
    'InteractivePlugIn',
    'NonInteractivePlugIn'
]
