import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Tuple, Any, List
from robot.api import logger

import warnings

import pandas as pd
from matplotlib import pyplot as plt

from system_trace.utils import get_error_info

warnings.filterwarnings("ignore")

INPUT_FMT = '%Y-%m-%d %H:%M:%S.%f'
OUTPUT_FMT = '%H:%M:%S'


def time_string_reformat_cb(from_format, to_format):
    def time_string_reformat(time_stamp):
        try:
            return datetime.strptime(time_stamp, from_format).strftime(to_format)
        except Exception as e:
            logger.error(f"Cannot convert time string: {time_stamp}")
    return time_string_reformat


class ChartAbstract(ABC):
    def __init__(self):
        self._verify_sql_query_for_variables()
        self._ext = '.png'

    def _verify_sql_query_for_variables(self):
        assert '{session_name}' in self.get_sql_query, "Variable '{session_name} missing query text"

    @property
    @abstractmethod
    def get_sql_query(self) -> str:
        raise NotImplementedError()

    def compose_sql_query(self, session_name, **kwargs) -> str:
        _sql = self.get_sql_query.format(session_name=session_name)
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
    def y_axes(self, data: [Iterable[Iterable]]):
        raise NotImplementedError()

    @staticmethod
    def x_axes(data, formatter=None):
        return [formatter(i) if formatter else i for i in data]

    @staticmethod
    def _get_y_limit(data):
        return max([max(y) for y in [x[1:] for x in data]])

    def generate_chart_data(self, query_results: Iterable[Iterable]) -> Tuple[str, List, Any, Iterable[Iterable]]:
        return tuple(
            (self.title,
             self.x_axes(query_results, time_string_reformat_cb(INPUT_FMT, OUTPUT_FMT)),
             self.y_axes(query_results),
             query_results)
        )

    def generate(self, sql_db, abs_image_path, sql: str, prefix=None, **marks):
        try:
            errors = []
            data_list = self.generate_chart_data(sql_db.execute(sql))
            for data in data_list:
                try:
                    title, x, y, chart_data = data
                    file_name = self.file_name.format(name=title.lower())
                    file_name = f"{prefix}_{file_name}" if prefix else file_name
                    file_path = os.path.join(abs_image_path, re.sub(r'\s+', '_', file_name))
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    plt.style.use('classic')
                    df = pd.DataFrame(chart_data, columns=y, index=x)
                    y_limit = self._get_y_limit(chart_data)
                    df.cumsum()
                    mp = df.plot(legend=True)
                    for label in mp.axes.get_xticklabels():
                        label.set_rotation(25)
                        label.set_x(10)
                    plt.ylim(0, y_limit * 1.3)
                    plt.xlabel('Time')
                    # TODO: Add vertical mark line on chart
                    # if len(marks) > 0:
                    #     fig, ax = plt.subplots()
                    #     for mark, time in marks.items():
                    #         ax.axvline(df.index.searchsorted(time),
                    #         color='red', linestyle="--", lw=2, label="lancement")
                    #     plt.tight_layout()
                    plt.savefig(file_path)
                    yield title.upper(), file_path
                except Exception as e:
                    errors.append(e)
        except Exception as e:
            f, l = get_error_info()
            raise RuntimeError(f"Probably SQL query failed; Reason: {e}; File: {f}:{l}")
        else:
            if len(errors) > 0:
                raise RuntimeError("Following sub charts creation error:\n\t{}".format(
                    '\n\t'.join([f"{i}. {e}" for i, e in enumerate(errors)])
                ))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            raise exc_type(exc_val, exc_tb)

