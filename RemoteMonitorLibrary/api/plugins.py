from abc import ABC

from robot.utils import is_truthy

from RemoteMonitorLibrary.model.chart_abstract import ChartAbstract
from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.model.runner_model import Parser, plugin_integration_abstract, plugin_runner_abstract,\
    FlowCommands, Variable
from RemoteMonitorLibrary.runner.ssh_runner import SSHLibraryPlugInWrapper, SSHLibraryCommand, \
    extract_method_arguments


class SSH_PlugInAPI(ABC, SSHLibraryPlugInWrapper, plugin_integration_abstract):
    __doc__ = """SSHLibraryCommand execution in background thread
    SSHLibraryCommand starting on adding to command pool within separate ssh session
    Output collecting during execution and sending to parsing and loading to data handler
    On connection interrupting command session restarting and output collecting continue
    """

    @staticmethod
    def normalise_arguments(prefix='return', func=is_truthy, **kwargs):
        for k in kwargs.keys():
            v = kwargs.get(k)
            if k.startswith(prefix):
                kwargs.update({k: func(v)})
        return kwargs


class Common_PlugInAPI(ABC, plugin_integration_abstract, plugin_runner_abstract):
    __doc__ = """Common plugin without specified action
    """


class ParseRC(Parser):
    def __init__(self, expected_rc=0):
        self._rc = expected_rc

    def __call__(self, output: dict) -> bool:
        rc = output.get('rc')
        assert rc == self._rc, f"Command result not match expected one (Result: {rc} vs. Expected: {self._rc})"


__all__ = ['SSH_PlugInAPI',
           'Common_PlugInAPI',
           'FlowCommands',
           SSHLibraryCommand.__name__,
           'extract_method_arguments',
           Parser.__name__,
           Variable.__name__,
           ParseRC.__name__,
           ChartAbstract.__name__,
           Configuration.__name__
           ]
