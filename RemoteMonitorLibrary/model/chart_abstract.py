import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Tuple, Any

from robotbackground_custom_logger import logger

warnings.filterwarnings("ignore")

INPUT_FMT = '%Y-%m-%d %H:%M:%S'
OUTPUT_FMT = '%H:%M:%S'


def time_string_reformat_cb(from_format, to_format):
    def time_string_reformat(time_stamp):
        try:
            return datetime.strptime(time_stamp, from_format).strftime(to_format)
        except Exception as e:
            logger.error(f"Cannot convert time string: {time_stamp}")
    return time_string_reformat


class ChartAbstract(ABC):
    def __init__(self, *sections):
        self._sections = sections
        self._verify_sql_query_for_variables()
        self._ext = '.png'

    def _verify_sql_query_for_variables(self):
        assert '{host_name}' in self.get_sql_query, "Variable '{host_name} missing query text"

    @property
    def sections(self):
        return self._sections

    @property
    @abstractmethod
    def get_sql_query(self) -> str:
        raise NotImplementedError()

    def compose_sql_query(self, host_name, **kwargs) -> str:
        _sql = self.get_sql_query.format(host_name=host_name)
        _start = kwargs.get('start_mark', None)
        if _start:
            _sql += f" AND \"{_start}\" <= t.TimeStamp"

        _end = kwargs.get('end_mark', None)
        if _end:
            _sql += f" AND \"{_end}\" >= t.TimeStamp"
        return _sql

    @property
    @abstractmethod
    def file_name(self) -> str:
        raise NotImplementedError()

    @property
    def title(self):
        return self.__class__.__name__

    @abstractmethod
    def y_axes(self, data: [Iterable[Iterable]]) -> Iterable[Any]:
        return [r[0] for r in data]

    @staticmethod
    def x_axes(data, time_columns=0, formatter=time_string_reformat_cb(INPUT_FMT, OUTPUT_FMT)) -> Iterable[Any]:
        return [formatter(i[time_columns]) if formatter else i[0] for i in data]

    @staticmethod
    def data_area(data: [Iterable[Iterable]]) -> [Iterable[Iterable]]:
        return [r[1:] for r in data]

    def generate_chart_data(self, query_results: Iterable[Iterable], extension=None) \
            -> Iterable[Tuple[str, Iterable, Iterable, Iterable[Iterable]]]:
        title = self.title + (f'_{extension}' if extension else '')
        return (title, self.x_axes(query_results), self.y_axes(query_results),
                self.data_area(query_results)),

