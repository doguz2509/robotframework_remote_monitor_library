from typing import Iterable, Tuple

from system_trace.api import plugin
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


class my_address(plugin.NonInteractivePlugIn):
    @property
    def affiliated_tables(self) -> Tuple[model.Table]:
        return Address(), Employment()

    @property
    def commands(self):
        return 'ls -l',

    def parse(self, command_output: str) -> Iterable[Tuple]:
        return Address().template('Dmitry', 'Oguz', 'Holon'), \
               Employment().template('Morphisec', 'BsH', '09.2020', None)


class my_job(plugin.NonInteractivePlugIn):
    @property
    def affiliated_tables(self) -> Tuple[model.Table]:
        return Employment(),

    @property
    def commands(self):
        return 'ls -l',

    def parse(self, command_output: str) -> Iterable[Tuple]:
        return Employment().template('Morphisec', 'BsH', '09.2020', None),


__all__ = [my_address, my_job]
