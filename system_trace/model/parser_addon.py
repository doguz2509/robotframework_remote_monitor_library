from abc import ABC, abstractmethod
from typing import AnyStr


class parser_addon_abstract(ABC):
    @abstractmethod
    def parse(self, command_output):
        raise NotImplementedError()

    @abstractmethod
    @property
    def table_schema(self) -> AnyStr:
        raise NotImplementedError()
