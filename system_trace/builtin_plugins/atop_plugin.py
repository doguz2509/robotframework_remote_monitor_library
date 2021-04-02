import json
import re
from collections import namedtuple, OrderedDict
from typing import Tuple, Iterable, List, Any

from robot.api import logger
from robot.utils import timestr_to_secs

from system_trace.api import BgLogger, TableSchemaService
from system_trace.api import model, plugins
from system_trace.model.chart_model.chart_abstract import ChartAbstract, time_string_reformat_cb, INPUT_FMT, OUTPUT_FMT
from system_trace.utils import Size
from system_trace.utils import get_error_info


class atop_system_level(model.Table):
    def __init__(self):
        model.Table.__init__(self, name='atop_system_level',
                             fields=[model.Field('Type'),
                                     model.Field('DataMap'),
                                     model.Field('Col1', model.FieldType.Real),
                                     model.Field('Col2', model.FieldType.Real),
                                     model.Field('Col3', model.FieldType.Real),
                                     model.Field('Col4', model.FieldType.Real),
                                     model.Field('Col5', model.FieldType.Real),
                                     model.Field('SUB_ID')])


class aTopSystemLevel(ChartAbstract):
    def __init__(self, *sections):
        self._sections = sections
        ChartAbstract.__init__(self)

    def y_axes(self, data: [Iterable[Iterable]]):
        pass

    @property
    def file_name(self) -> str:
        return "{name}.png"

    @property
    def get_sql_query(self) -> str:
        return """select top.SUB_ID as SUB_ID, top.DataMap as Map, t.TimeStamp as Time, top.Col1 as Col1, 
                top.Col2 as Col2, top.Col3 as Col3, top.Col4 as Col4, top.Col5 as Col5
                from aTopSystemLevel top
                JOIN Sessions s ON t.REF_TO_SESSION = s.SESSION_ID
                JOIN TimeReference t ON top.REF_TO_TS = t.TS_ID 
                WHERE s.Title = '{session_name}' """

    def generate_chart_data(self, query_results: Iterable[Iterable]) -> Tuple[str, List, Any, Iterable[Iterable]]:
        result = []
        for type_ in set([i[0] for i in query_results if any([i[0].startswith(section) for section in self._sections])]):
            try:
                data = [i[1:] for i in query_results if i[0] == type_]
                x_axes = self.x_axes([i[1] for i in data], time_string_reformat_cb(INPUT_FMT, OUTPUT_FMT))
                y_axes = [i for i in json.loads([y[0] for y in data][0]) if i not in ['no', 'SUB_ID']]
                data = [i[2:] for i in data]
                data = [u[0:len(y_axes)] for u in data]
                chart_data = f"{type_}", x_axes, y_axes, data
                # yield f"{type_}", x_axes, y_axes, [u[0:len(y_axes)] for u in data]
                logger.debug("Create chart data: {}\n{}\n{}\n{} entries".format(type_, x_axes, y_axes, len(data)))
                result.append(chart_data)
            except Exception as e:
                f, l = get_error_info()
                logger.error(f"Chart generation error: {e}; File: {f}:{l}")
        return result


def try_time_string_to_secs(time_str):
    try:
        return timestr_to_secs(time_str)
    except Exception:
        return -1


def _normalize_line(*cells):
    try:
        result_tuple = [s.strip().replace('#', '') for s in cells if len(s.strip()) > 0]
        type_, col1, col2, col3, col4, col5 = result_tuple
    except ValueError:
        type_, col1, col2, col4, col5 = result_tuple
        col3 = 'swcac   0'
    except Exception as e:
        raise
    finally:
        data_ = col1, col2, col3, col4, col5
    return type_, data_


def _generate_atop_system_level(input_text, columns_template, *defaults):
    header_regex = re.compile(r'(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|')
    res = []
    row_mapping = namedtuple('ROW', ('Col1', 'Col2', 'Col3', 'Col4', 'Col5', 'SUB_ID'))
    for line in header_regex.findall(input_text):
        try:
            type_, data_ = _normalize_line(*line)
            sub_id = type_
            pattern = OrderedDict()
            if type_ in ('PRC', 'PAG'):
                pattern.update(
                    **{k: try_time_string_to_secs(v) for k, v in [re.split(r'\s+', s.strip(), 2) for s in data_]})
            elif type_ in ['CPU', 'cpu']:
                pattern.update(
                    **{k: v.replace('%', '') for k, v in [re.split(r'\s+', s.strip(), 1) for s in data_]})
                if type_ == 'cpu':
                    for k, v in pattern.items():
                        if k.startswith('cpu'):
                            _cpu_str, _wait = re.split(r'\s+', v, 1)
                            pattern.pop(k)
                            pattern.update({'wait': _wait})
                            sub_id = k.replace('cpu', 'cpu_').upper()
                            break
                    type_ = 'CPU'
                else:
                    sub_id = 'CPU_All'
            elif type_ == 'CPL':
                pattern.update(
                    **{k: v for k, v in [re.split(r'\s+', s.strip(), 1) for s in data_]})
            elif type_ in ['MEM', 'SWP']:
                pattern.update(
                    **{k: v for k, v in [re.split(r'\s+', s.strip(), 1) for s in data_]})
                for k in pattern.keys():
                    pattern[k] = Size(pattern[k]).set_format('M').number
            elif type_ in ['LVM', 'DSK', 'NET']:
                items = [re.split(r'\s+', s.strip(), 1) for s in data_]
                for item in items:
                    if len(item) == 1 or item[1] == '----':
                        pattern.update({'source': '-1'})
                        sub_id = f"{type_}_{item[0]}"
                    else:
                        pattern.update({item[0]: re.sub(r'[\sKbpms%]+', '', item[1])})
            else:
                raise TypeError(f"Unknown line type: {' '.join(line)}")
            pattern.update(SUB_ID=sub_id)
            res.append(columns_template(
                *[*defaults, type_, json.dumps(row_mapping(*pattern.keys()), indent=True), *pattern.values()]))
        except ValueError as e:
            BgLogger.error(f"aTop parse error: {e}")
        except Exception as e:
            f, l = get_error_info()
            BgLogger.error("aTop unknown parse error: {}; File: {}:{}\n{}".format(e, f, l, line))
            raise
    return res


class aTopPlugIn(plugins.PlugInAPI):

    SYNC_DATE_FORMAT = '%Y%m%d %H:%M:%S'

    def __init__(self, parameters, data_handler):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, persistent=True)
        self.file = 'atop.dat'
        self.folder = '~/atop_temp'
        self._time_delta = None

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return atop_system_level(),

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return aTopSystemLevel('CPU'), aTopSystemLevel('CPL', 'MEM', 'PRC', 'PAG'), aTopSystemLevel('LVM'), \
               aTopSystemLevel('DSK', 'SWP'), aTopSystemLevel('NET')

    def parse(self, command_output):
        table_template = self.affiliated_tables()[0].template
        data = _generate_atop_system_level(command_output, table_template)
        self._data_handler(model.DataUnit(TableSchemaService().tables.atop_system_level, *data))

    @property
    def setup(self) -> plugins.CommandsType:

        return [plugins.Command('killall -9 atop', sudo=True),
                plugins.Command(f'rm -rf {self.folder}', sudo=True),
                plugins.Command(f'mkdir -p {self.folder}', sudo=True),
                plugins.Command(f'atop -w {self.folder}/{self.file} {int(self.interval)} &',
                                sudo=True, interactive=True),
                ]

    @property
    def periodic_commands(self):
        return plugins.Command(f'atop -r {self.folder}/{self.file} -b `date +%H:%M:%S` -e `date +%H:%M:%S`|tee',
                               sudo=True, parser=self.parse),

    @property
    def teardown(self) -> plugins.CommandsType:
        return plugins.Command('killall -9 atop', sudo=True),


__all__ = ['aTopPlugIn']
