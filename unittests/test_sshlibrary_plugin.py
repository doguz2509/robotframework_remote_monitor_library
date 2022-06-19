from unittest import TestCase

from RemoteMonitorLibrary.model.configuration import Configuration
from RemoteMonitorLibrary.plugins_modules.sshlibrary_plugin import SSHLibrary

parameters = Configuration(alias='unittest', username='vagrant', password='vagrant', host='192.168.25.46')


class TestSSHLibrary(TestCase):
    def test_command_provided(self):
        with self.assertRaises(TypeError) as e:
            s = SSHLibrary(parameters.parameters, print, host_id=1)
        print(f"Raised as expected - TypeError")

    def test_rc_provided(self):
        try:
            s = SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, rc=0)
        except AssertionError as e:
            assert "For verify RC argument 'return_rc' must be provided" == f"{e}", \
                f"Error not match '{e}' vs. expected: For verify RC argument 'return_rc' must be provided"
            print(f"Raised as expected: {e}")

    def test_expected_provided(self):
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, expected='bla')
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, expected='bla', return_stdout='yes')
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, expected='bla',
                   return_stdout='no', return_stderr='yes')
        exp_err = "For verify expected pattern one of arguments 'return_stdout' or 'return_stderr' must be provided"
        for arg_set in (dict(expected='bla', return_stdout='no'), dict(expected='bla', return_stdout='no',
                                                                       return_stderr='no')):
            try:
                SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, **arg_set)
            except AssertionError as e:
                assert exp_err == f"{e}", f"{e}"
                print(f"Raised as expected -> Arguments: {arg_set}; Error: {e}")

    def test_prohibited_provided(self):
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, prohibited='bla')
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, prohibited='bla', return_stdout='yes')
        SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1, prohibited='bla',
                   return_stdout='no', return_stderr='yes')
        exp_err = "For verify expected pattern one of arguments 'return_stdout' or 'return_stderr' must be provided"
        for arg_set in (dict(prohibited='bla', return_stdout='no'), dict(prohibited='bla', return_stdout='no',
                                                                         return_stderr='no')):
            try:
                SSHLibrary(parameters.parameters, print, 'ls -l', host_id=1,**arg_set)
            except AssertionError as e:
                assert exp_err == f"{e}", f"{e}"
                print(f"Raised as expected -> Arguments: {arg_set}; Error: {e}")
