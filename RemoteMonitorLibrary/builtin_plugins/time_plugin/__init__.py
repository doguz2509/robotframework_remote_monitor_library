from .runner import Time

__doc__ = """
=== Time plugin overview ===
    Wrap linux /usr/bin/time utility for periodical execution and monitor of customer command for process io, memory, cpu, etc
        
    Full documentation for time utility available on [https://linux.die.net/man/1/time|time man(1)]
    
    === Plugin parameters === 
    
    Parameters can be supplied via keyword `Start monitor plugin` as key-value pairs
    
    Time plugin arguments:
    
    - command: command to be executed and measured by time (Mandatory)
    
    | /usr/bin/time -f "%... all time format fields (see man)" 'command' > /dev/null
      
      Note: Pay attention not to redirect command stderr to stdout (avoid '2>&1'); Time write to stderr by itself and it send to parser
      
    - name: User friendly alias for command (Optional)
    - start_in_folder: path to executable binary/script if execution by path not relevant (Optional)
      
      If provided command will be executed as following:
        
    | cd 'start_in_folder' ; /usr/bin/time -f "" 'command' > /dev/null
    
    - sudo: True if sudo required, False if omitted (Optional)
    - sudo_password: True if password required for sudo, False if omitted (Optional)
    
      On plugin start sudo and sudo_password will be replace with sudo password provided for connection module

"""


__all__ = [
    Time.__name__,
    __doc__
]
