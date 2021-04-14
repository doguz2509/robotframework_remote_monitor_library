from .runner import aTop

__doc__ = """
=== aTop linux utility overview === 

Wrap aTop utility for periodical measurement of system io, memory, cpu, etc. by aTop utility.  
Full atop documentation available on [https://linux.die.net/man/1/atop|atop man(1)]. 
Remote Monitor starting by command  'sudo atop -w ~/atop_temp/atop.dat <interval>'

aTop Arguments:
- interval: can be define from keyword `Start monitor plugin` as key-value pair (Default: 1s) 

Note: Support robot time string (1s, 05m, etc.)

"""

__all__ = [
    aTop.__name__,
    __doc__
]
