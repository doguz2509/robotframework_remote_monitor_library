import json
import re
from collections import namedtuple, OrderedDict
from typing import Iterable, Tuple, List, Any

from SSHLibrary import SSHLibrary
from robot.api import logger
from robot.utils import timestr_to_secs

from RemoteMonitorLibrary.api import plugins, model, tools
from RemoteMonitorLibrary.api.plugins import ChartAbstract
from RemoteMonitorLibrary.utils import Size, get_error_info

__doc__ = """
== aTop plugin overview == 

Wrap aTop utility for periodical measurement of system io, memory, cpu, etc. by aTop utility.  

Full atop documentation available on [https://linux.die.net/man/1/atop|atop man(1)]. 

Remote Monitor starting by command  

| sudo atop -w ~/atop_temp/atop.dat <interval>

Reading atop statistics made with command

| sudo atop -r ~/atop_temp/atop.dat -b  -b `date +%Y%m%d%H%M` 

!!! Pay attention: Ubuntu & CentOS supported only for now !!! 

aTop Arguments:
- interval: can be define from keyword `Start monitor plugin` as key-value pair (Default: 1s) 

Note: Support robot time format string (1s, 05m, etc.)

"""


class atop_system_level_table(model.TimeReferencedTable):
    def __init__(self):
        model.TimeReferencedTable.__init__(self, name='atop_system_level',
                                           fields=[model.Field('Type'),
                                                   model.Field('DataMap'),
                                                   model.Field('Col1', model.FieldType.Real),
                                                   model.Field('Col2', model.FieldType.Real),
                                                   model.Field('Col3', model.FieldType.Real),
                                                   model.Field('Col4', model.FieldType.Real),
                                                   model.Field('Col5', model.FieldType.Real),
                                                   model.Field('SUB_ID')])


class aTopSystemLevelChart(ChartAbstract):
    def __init__(self, *sections):
        self._sections = sections
        ChartAbstract.__init__(self, *sections)

    @property
    def sections(self):
        return self._sections

    def y_axes(self, data: [Iterable[Any]]) -> Iterable[Any]:
        return [i for i in json.loads([y[0] for y in data][0]) if i not in ['no', 'SUB_ID']]

    def data_area(self, data: [Iterable[Iterable]]) -> [Iterable[Iterable]]:
        return data

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
                x_axes = self.x_axes(data, 1)
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


class aTopParser(plugins.Parser):
    def __init__(self, **kwargs):
        plugins.Parser.__init__(self, **kwargs)
        self._ts_cache = tools.CacheList(int(600 / timestr_to_secs(kwargs.get('interval', '1x'))))

    @staticmethod
    def try_time_string_to_secs(time_str):
        try:
            return timestr_to_secs(time_str)
        except Exception:
            return -1

    @staticmethod
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

    @staticmethod
    def _generate_atop_system_level(input_text, columns_template, *defaults):
        header_regex = re.compile(r'(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|')
        res = []
        row_mapping = namedtuple('ROW', ('Col1', 'Col2', 'Col3', 'Col4', 'Col5', 'SUB_ID'))
        for line in header_regex.findall(input_text):
            try:
                type_, data_ = aTopParser._normalize_line(*line)
                sub_id = type_
                pattern = OrderedDict()
                if type_ in ('PRC', 'PAG'):
                    pattern.update(
                        **{k: aTopParser.try_time_string_to_secs(v) for k, v in
                           [re.split(r'\s+', s.strip(), 2) for s in data_]})
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
                    data = self._generate_atop_system_level('\n'.join(lines), table_template, self.host_id, None)
                    self._ts_cache.append(ts)
                    self.data_handler(model.DataUnit(self.table, *data))

        except Exception as e:
            f, li = get_error_info()
            tools.Logger().error(
                f"{self.__class__.__name__}: Unexpected error: {type(e).__name__}: {e}; File: {f}:{li}")
        else:
            return True
        return False


class aTop(plugins.PlugInAPI):
    OS_DATE_FORMAT = {
        'ubuntu': '%H:%M',
        'centos': '%Y%m%d%H%M'
    }

    def __init__(self, parameters, data_handler, *args, **user_options):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, *args, **user_options)
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
            SSHLibrary.execute_command,
            f"atop -r {self.folder}/{self.file} -b `date +{self.OS_DATE_FORMAT[self.os_name]}`",
            sudo=True, sudo_password=True, return_rc=True, return_stderr=True,
            parser=aTopParser(host_id=self.host_id, table=self.affiliated_tables()[0],
                              data_handler=self._data_handler, counter=self.iteration_counter,
                              interval=self.parameters.interval)),

    @property
    def teardown(self):
        return plugins.SSHLibraryCommand(SSHLibrary.execute_command, 'killall -9 atop', sudo=True, sudo_password=True),


__all__ = [
    aTop.__name__,
    __doc__
]