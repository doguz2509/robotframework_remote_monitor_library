from typing import Iterable, Any, Tuple

from SystemTraceLibrary.api import plugins, model


class TimeChart(plugins.ChartAbstract):
    def __init__(self, table: model.Table, title, *sections):
        self._table = table
        plugins.ChartAbstract.__init__(self, *(sections if len(sections) > 0 else self._table.columns))
        self._title = title

    @property
    def sections(self):
        return self._sections

    @property
    def title(self):
        return self._title

    @property
    def file_name(self) -> str:
        return "{name}.png"

    @property
    def get_sql_query(self) -> str:
        return """
        SELECT t.TimeStamp as TimeStamp, {select}, n.Command
        FROM {table_name} n
        JOIN TraceHost h ON n.HOST_REF = h.HOST_ID
        JOIN TimeLine t ON n.TL_REF = t.TL_ID
        WHERE h.HostName = '{{host_name}}'""".format(select=', '.join([f"n.{c} as {c}" for c in self.sections]),
                                                     table_name=self._table.name)

    def y_axes(self, data: [Iterable[Iterable]]) -> Iterable[Any]:
        return self.sections

    def __str__(self):
        return f"{self.__class__.__name__}: {', '.join(self.sections)}"

    def generate_chart_data(self, query_results: Iterable[Iterable]) -> \
            Iterable[Tuple[str, Iterable, Iterable, Iterable[Iterable]]]:

        data_series = {}
        for row in query_results:
            if row[-1] not in data_series.keys():
                data_series.update({row[-1]: []})
            data_series[row[-1]].append(row[:-1])
        result = []
        for cmd, row in data_series.items():
            result.append(super().generate_chart_data(row, cmd)[0])
        return result

