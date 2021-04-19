
from .runner import SSHLibrary


__doc__ = """=== SSHLibrary plugin ===
Allow running repeatable ssh remote command within connection monitor

    Arguments:
    
    All arguments related for the following keywords:
    
        | execute_command
        | start_command
    
    !!! Note: rest keywords (Such as: write, writebare, readoutput) not tested at all !!!
    
"""

__all__ = [
    '__doc__',
    'SSHLibrary'
]
