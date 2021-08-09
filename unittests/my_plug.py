from typing import Tuple

from SSHLibrary import SSHLibrary

import RemoteMonitorLibrary.model.runner_model.runner_model

import RemoteMonitorLibrary.runner.ssh_runner
from RemoteMonitorLibrary.api import model
from RemoteMonitorLibrary.api import plugins


class Address(model.Table):
    def __init__(self):
        super().__init__(fields=[
            model.Field('name'),
            model.Field('family'),
            model.Field('address'),
        ])


class Employment(model.Table):
    def __init__(self):
        super().__init__(fields=[
            model.Field('Company'),
            model.Field('address'),
            model.Field('start'),
            model.Field('end')
        ])


class my_address(plugins.SSH_PlugInAPI):
    @staticmethod
    def affiliated_tables() -> Tuple[model.Table]:
        return Address(), Employment()

    @property
    def periodic_commands(self):
        return RemoteMonitorLibrary.runner.ssh_runner.SSHLibraryCommand('ls -l'), \
               plugins.ReadOutput(SSHLibrary.read_until, 'ls', loglevel='DEBUG')

    @staticmethod
    def parse(data_handler, affiliated_tables: Tuple[model.Table], command_output: str):
        data_handler(Address().template('Dmitry', 'Oguz', 'Holon'))
        data_handler(Employment().template('Morphisec', 'BsH', '09.2020', None))


class my_job(plugins.SSH_PlugInAPI):
    @staticmethod
    def affiliated_tables() -> Tuple[model.Table]:
        return Employment(),

    @property
    def periodic_commands(self):
        return RemoteMonitorLibrary.runner.ssh_runner.SSHLibraryCommand('ls -l'),

    @staticmethod
    def parse(data_handler, affiliated_tables: Tuple[model.Table], command_output) -> bool:
        data_handler(Employment().template('Morphisec', 'BsH', '09.2020', None))


__all__ = [my_address, my_job]


if __name__ == '__main__':
    from robot.utils import DotDict
    m = my_address(DotDict(alias='asdas', interval=5, fault_tolerance=10), print, host_id=1)
    c = m.periodic_commands()

    for com in c:
        print(f"{com}")
    print('')
