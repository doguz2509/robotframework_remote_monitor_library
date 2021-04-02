from typing import Iterable, Tuple

from system_trace.api import plugins
from system_trace.api import model


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


class my_address(plugins.PlugInAPI):
    @staticmethod
    def affiliated_tables() -> Tuple[model.Table]:
        return Address(), Employment()

    @property
    def periodic_commands(self):
        return plugins.Command('ls -l'),

    @staticmethod
    def parse(data_handler, affiliated_tables: Tuple[model.Table], command_output: str):
        data_handler(Address().template('Dmitry', 'Oguz', 'Holon'))
        data_handler(Employment().template('Morphisec', 'BsH', '09.2020', None))


class my_job(plugins.PlugInAPI):
    @staticmethod
    def affiliated_tables() -> Tuple[model.Table]:
        return Employment(),

    @property
    def periodic_commands(self):
        return plugins.Command('ls -l'),

    @staticmethod
    def parse(data_handler, affiliated_tables: Tuple[model.Table], command_output) -> bool:
        data_handler(Employment().template('Morphisec', 'BsH', '09.2020', None))


__all__ = [my_address, my_job]
