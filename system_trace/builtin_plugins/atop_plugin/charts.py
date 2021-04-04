import json
from typing import Iterable, Tuple, List, Any

from robot.api import logger

from system_trace.api.plugins import ChartAbstract
from system_trace.utils import get_error_info


class aTopSystemLevelChart(ChartAbstract):
    def __init__(self, *sections):
        self._sections = sections
        ChartAbstract.__init__(self)

    def y_axes(self, data: [Iterable[Any]]) -> Iterable[Any]:
        return [i for i in json.loads([y[0] for y in data][0]) if i not in ['no', 'SUB_ID']]

    @property
    def file_name(self) -> str:
        return "{name}.png"

    @property
    def get_sql_query(self) -> str:
        return """select top.SUB_ID as SUB_ID, top.DataMap as Map, t.TimeStamp as Time, top.Col1 as Col1, 
                top.Col2 as Col2, top.Col3 as Col3, top.Col4 as Col4, top.Col5 as Col5
                from atop_system_level top
                JOIN TraceHost h ON top.HOST_REF = h.HOST_ID
                JOIN TimeLine t ON top.TL_REF = t.TL_ID 
                WHERE h.HostName = '{host_name}' """

    def generate_chart_data(self, query_results: Iterable[Iterable]) \
            -> List[Tuple[str, Iterable, Iterable, Iterable[Iterable]]]:
        result = []
        for type_ in set(
                [i[0] for i in query_results if any([i[0].startswith(section) for section in self._sections])]):
            try:
                data = [i[1:] for i in query_results if i[0] == type_]
                x_axes = self.x_axes([i[1] for i in data])
                y_axes = self.y_axes(data)
                data = [i[2:] for i in data]
                data = [u[0:len(y_axes)] for u in data]
                chart_data = f"{type_}", x_axes, y_axes, data
                logger.debug("Create chart data: {}\n{}\n{}\n{} entries".format(type_, x_axes, y_axes, len(data)))
                result.append(chart_data)
            except Exception as e:
                f, l = get_error_info()
                logger.error(f"Chart generation error: {e}; File: {f}:{l}")
        return result

