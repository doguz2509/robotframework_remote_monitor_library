
from .runner import SSHLibrary


__doc__ = """== SSHLibrary plugin ===
Allow running repeatable ssh remote command within connection monitor

    Arguments:
    - SSHLibrary methods:
    
        execute_command
        
        start_command
    
    With all related arguments 
    - name: Particular command alias [Optional]
    - 
"""

__all__ = [
    '__doc__',
    'SSHLibrary'
]
