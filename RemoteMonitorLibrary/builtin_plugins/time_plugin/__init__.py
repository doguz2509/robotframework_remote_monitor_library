from .runner import Time

__doc__ = """
=== Time plugin overview ===
    Wrap linux /usr/bin/time utility for periodical execution and monitor of customer command for process io, memory, cpu, etc
        
    Full documentation for time utility available on [https://linux.die.net/man/1/time|time man(1)]
    
    === Plugin parameters === 
    
    Parameters can be supplied via keyword `Start monitor plugin` as key-value pairs
    
    Time plugin arguments:
    - command: Command to be executed by /usr/bin/time (Mandatory)
      
      Note: Pay attention not to redirect stderr to stdout; Time write to stderr by itself and it send to parser
      
    - name: User friendly alias for command (Optional)
    - start_folder: path to executable binary/script if execution by path not relevant (Optional)
    - sudo: True if sudo required, False if omitted (Optional)
    - sudo_password: True if password required for sudo, False if omitted (Optional)

"""


__all__ = [
    Time.__name__,
    __doc__
]
