import json
import re
from collections import namedtuple, OrderedDict
from typing import Iterable

from robot.utils import timestr_to_secs

from system_trace.api import Logger, plugins, model
from system_trace.utils import Size, get_error_info
from .charts import aTopSystemLevelChart
from .tables import atop_system_level_table


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
            Logger.error(f"aTop parse error: {e}")
        except Exception as e:
            f, l = get_error_info()
            Logger.error("aTop unknown parse error: {}; File: {}:{}\n{}".format(e, f, l, line))
            raise
    return res


class aTopPlugIn(plugins.PlugInAPI):
    SYNC_DATE_FORMAT = '%Y%m%d %H:%M:%S'

    def __init__(self, parameters, data_handler, host_id, **kwargs):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, host_id=host_id, **kwargs)
        self.file = 'atop.dat'
        self.folder = '~/atop_temp'
        self._time_delta = None

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return atop_system_level_table(),

    @staticmethod
    def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
        return aTopSystemLevelChart('CPU'), aTopSystemLevelChart('CPL', 'MEM', 'PRC', 'PAG'), aTopSystemLevelChart('LVM'), \
               aTopSystemLevelChart('DSK', 'SWP'), aTopSystemLevelChart('NET')

    def parse(self, command_output):
        table_template = self.affiliated_tables()[0].template
        data = _generate_atop_system_level(command_output, table_template, self.host_id, None)
        self._data_handler(model.DataUnit(self.affiliated_tables()[0], *data))

    @property
    def setup(self) -> plugins.CommandsType:
        return [plugins.Command('killall -9 atop', sudo=True),
                plugins.Command(f'rm -rf {self.folder}', sudo=True),
                plugins.Command(f'mkdir -p {self.folder}', sudo=True),
                plugins.Command("{nohup} atop -w {folder}/{file} {interval} &".format(
                    nohup='' if self.persistent else 'nohup',
                    folder=self.folder,
                    file=self.file,
                    interval=int(self.interval)), sudo=True, interactive=True)
                ]

    @property
    def periodic_commands(self):
        return plugins.Command(f'atop -r {self.folder}/{self.file} -b `date +%H:%M:%S` -e `date +%H:%M:%S`|tee',
                               sudo=True, parser=self.parse),

    @property
    def teardown(self) -> plugins.CommandsType:
        return plugins.Command('killall -9 atop', sudo=True),


__all__ = [aTopPlugIn.__name__]
