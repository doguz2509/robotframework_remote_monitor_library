from abc import ABCMeta, abstractmethod

from RemoteMonitorLibrary.model import Parser
from RemoteMonitorLibrary.model.runner_model import Variable


class CommandUnit(metaclass=ABCMeta):
    def __init__(self, options: dict):
        self._parser: Parser = options.pop('parser', None)
        if self.parser:
            assert isinstance(self.parser, Parser), f"Parser type error [Error type: {type(self.parser).__name__}]"

        self._variable_setter = options.pop('variable_setter', None)
        if self._variable_setter:
            assert isinstance(self._variable_setter, Variable), "Variable setter type error"

        self._variable_getter = options.pop('variable_getter', None)
        if self._variable_getter:
            assert isinstance(self.variable_getter, Variable), "Variable getter vtype error"

    @abstractmethod
    def __str__(self):
        pass

    @property
    def variable_setter(self):
        return self._variable_setter

    @property
    def variable_getter(self):
        return self._variable_getter

    @property
    def parser(self):
        return self._parser

    def parse(self, output: dict):
        if self.parser:
            self.parser(output)
        if self.variable_setter:
            self.variable_setter(output)
