import json
import re
from collections import namedtuple, OrderedDict
from enum import Enum
from typing import Iterable

from SSHLibrary import SSHLibrary
from robot.utils import timestr_to_secs

from RemoteMonitorLibrary.api import plugins, model, tools
from RemoteMonitorLibrary.utils import Size, get_error_info

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
                items = [re.split(r'\s+', s.strip()) for s in data_]
                for item in items:
                    if len(item) == 1 or item[1] == '----':
                        pattern.update({'source': '-1'})
                        sub_id = f"{type_}_{item[0]}"
                    elif len(item) >= 2:
                        pattern.update({item[0]: item[1].replace('%', '')})
                    else:
                        pattern.update({item[0]: re.sub(r'[\sKbpms%]+', '', item[1])})
            else:
                raise TypeError(f"Unknown line type: {' '.join(line)}")
            pattern.update(SUB_ID=sub_id)
            res.append(columns_template(
                *[*defaults, type_, json.dumps(row_mapping(*pattern.keys()), indent=True), *pattern.values()]))
        except ValueError as e:
            tools.Logger().error(f"aTop parse error: {e}")
        except Exception as e:
            f, l = get_error_info()
            tools.Logger().error("aTop unknown parse error: {}; File: {}:{}\n{}".format(e, f, l, line))
            raise
    return res


class aTopParser(plugins.Parser):
    def __init__(self, **kwargs):
        plugins.Parser.__init__(self, **kwargs)
        self._ts_cache = tools.CacheList(int(600 / timestr_to_secs(kwargs.get('interval', '1x'))))

    def __call__(self, output) -> bool:
        table_template = self.table.template
        try:
            stdout = output.get('stdout')
            stderr = output.get('stderr')
            rc = output.get('rc')
            assert rc == 0, f"Last {self.__class__.__name__} ended with rc: {rc}\n{stderr}"
            for atop_portion in [e.strip() for e in stdout.split('ATOP') if e.strip() != '']:
                lines = atop_portion.splitlines()
                f_line = lines.pop(0)
                ts = '_'.join(re.split(r'\s+', f_line)[2:4])
                if ts not in self._ts_cache:
                    data = _generate_atop_system_level('\n'.join(lines), table_template, self.host_id, None)
                    self._ts_cache.append(ts)
                    self.data_handler(model.DataUnit(self.table, *data))

        except Exception as e:
            f, li = get_error_info()
            tools.Logger().error(
                f"{self.__class__.__name__}: Unexpected error: {type(e).__name__}: {e}; File: {f}:{li}")
        else:
            return True
        return False


class DateFormat(Enum):
    ubuntu = '%H:%M'
    centos = '%Y%m%d%H%M'


class aTop(plugins.PlugInAPI):
    def __init__(self, parameters, data_handler, **user_options):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, **user_options)
        self.file = 'atop.dat'
        self.folder = '~/atop_temp'
        self._time_delta = None
        self._os_name = None

    @property
    def os_name(self):
        return self._os_name

    @staticmethod
    def _get_os_name(ssh_client: SSHLibrary):
        out, err, rc = ssh_client.execute_command("cat /etc/os-release|grep -E '^ID='|awk -F'=' '{print$2}'",
                                                  return_rc=True, return_stderr=True)
        assert rc == 0, "Cannot occur OS name"
        out = out.replace(r'"', '')
        tools.Logger().debug(f"OS resolved: {out}")
        return out

    def __enter__(self):
        _ssh = super().__enter__()
        self._os_name = self.os_name or self._get_os_name(_ssh)
        return _ssh

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return atop_system_level_table(),

    @staticmethod
    def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
        return aTopSystemLevelChart('CPU'), aTopSystemLevelChart('CPL', 'MEM', 'PRC', 'PAG'), aTopSystemLevelChart(
            'LVM'), \
               aTopSystemLevelChart('DSK', 'SWP'), aTopSystemLevelChart('NET')

    @property
    def setup(self):
        return plugins.SSHLibraryCommand(SSHLibrary.execute_command, 'killall -9 atop', sudo=self.sudo_expected,
                                         sudo_password=self.sudo_password_expected), \
               plugins.SSHLibraryCommand(SSHLibrary.execute_command, f'rm -rf {self.folder}', sudo=True,
                                         sudo_password=True), \
               plugins.SSHLibraryCommand(SSHLibrary.execute_command, f'mkdir -p {self.folder}', sudo=self.sudo_expected,
                                         sudo_password=self.sudo_password_expected), \
               plugins.SSHLibraryCommand(SSHLibrary.start_command,
                                         "{nohup} atop -w {folder}/{file} {interval} &".format(
                                             nohup='' if self.persistent else 'nohup',
                                             folder=self.folder,
                                             file=self.file,
                                             interval=int(self.interval)),
                                         sudo=self.sudo_expected,
                                         sudo_password=self.sudo_password_expected)

    @property
    def periodic_commands(self):
        return plugins.SSHLibraryCommand(
            SSHLibrary.execute_command, f"atop -r {self.folder}/{self.file} -b `date +{DateFormat[self.os_name].value}`",
            sudo=True, sudo_password=True, return_rc=True, return_stderr=True,
            parser=aTopParser(host_id=self.host_id, table=self.affiliated_tables()[0],
                              data_handler=self._data_handler, counter=self.iteration_counter,
                              interval=self.parameters.interval)),

    @property
    def teardown(self):
        return plugins.SSHLibraryCommand(SSHLibrary.execute_command, 'killall -9 atop', sudo=True, sudo_password=True),
