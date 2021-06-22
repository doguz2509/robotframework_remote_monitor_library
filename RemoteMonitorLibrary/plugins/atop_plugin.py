import json
import re
from collections import namedtuple, OrderedDict
from datetime import datetime
from typing import Iterable, Tuple, List, Any, AnyStr, Dict

from robot.utils import timestr_to_secs

from SSHLibrary import SSHLibrary

from RemoteMonitorLibrary.utils.logger_helper import logger

from RemoteMonitorLibrary.api import model, tools, db
from RemoteMonitorLibrary.api.plugins import *
from RemoteMonitorLibrary.utils import Size, get_error_info, Singleton

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

Not named:
- processes names: provided process CPU & Memory data will be monitored
    
Named:
- interval: can be define from keyword `Start monitor plugin` as key-value pair (Default: 1s) 

Note: Support robot time format string (1s, 05m, etc.)

"""


class atop_system_level(model.PlugInTable):
    def __init__(self):
        super().__init__(name='atop_system_level')
        self.add_time_reference()
        self.add_field(model.Field('Type'))
        self.add_field(model.Field('DataMap'))
        self.add_field(model.Field('Col1', model.FieldType.Real))
        self.add_field(model.Field('Col2', model.FieldType.Real))
        self.add_field(model.Field('Col3', model.FieldType.Real))
        self.add_field(model.Field('Col4', model.FieldType.Real))
        self.add_field(model.Field('Col5', model.FieldType.Real))
        self.add_field(model.Field('SUB_ID'))


class atop_process_level(model.PlugInTable):
    def __init__(self):
        super().__init__(name='atop_process_level')
        self.add_time_reference()
        self.add_field(model.Field('PID', model.FieldType.Int))
        self.add_field(model.Field('SYSCPU', model.FieldType.Real))
        self.add_field(model.Field('USRCPU', model.FieldType.Real))
        self.add_field(model.Field('VGROW', model.FieldType.Real))
        self.add_field(model.Field('RGROW', model.FieldType.Real))
        self.add_field(model.Field('RDDSK', model.FieldType.Real))
        self.add_field(model.Field('WRDSK', model.FieldType.Real))
        self.add_field(model.Field('CPU', model.FieldType.Int))
        self.add_field(model.Field('CMD'))


@Singleton
class ProcessMonitorRegistry(dict):

    def __getitem__(self, plugin_id):
        self.setdefault(plugin_id, {})
        return super().__getitem__(plugin_id)

    def register(self, plugin_id, name, control=False):
        if name in self.get(plugin_id).keys():
            logger.warn(f"Process '{name}' already registered in {plugin_id}")
            return
        self[plugin_id].update({name: {'control': control, 'active': True}})

    def activate(self, plugin_id, name):
        data = self[plugin_id].get(name, None)
        assert data, f"Process '{name}' mot registered in '{plugin_id}"
        data.update(active=True)
        self[plugin_id].update({name: data})

    def deactivate(self, plugin_id, name):
        data = self[plugin_id].get(name, None)
        assert data, f"Process '{name}' mot registered in '{plugin_id}"
        data.update(active=False)
        self[plugin_id].update({name: data})


class aTopProcessLevelChart(ChartAbstract):
    @property
    def get_sql_query(self) -> str:
        return f"""SELECT t.TimeStamp, p.SYSCPU as SYSCPU, p.USRCPU, p.VGROW, p.RDDSK, p.WRDSK, p.CPU, p.CMD
            FROM atop_process_level p
            JOIN TraceHost h ON p.HOST_REF = h.HOST_ID
            JOIN TimeLine t ON p.TL_REF = t.TL_ID 
            WHERE h.HostName = '{{host_name}}'"""

    @property
    def file_name(self) -> str:
        return "process_{name}.png"

    def y_axes(self, data: [Iterable[Iterable]] = None) -> Iterable[Any]:
        return ['SYSCPU', 'USRCPU', 'VGROW', 'RDDSK', 'WRDSK', 'CPU']

    def generate_chart_data(self, query_results: Iterable[Iterable], extension=None) -> \
            Iterable[Tuple[str, Iterable, Iterable, Iterable[Iterable]]]:
        result = []
        for plugin, processes in ProcessMonitorRegistry().items():
            for process in [p for p in processes.keys()]:
                data = [entry[0:6] for entry in query_results if process in entry[7]]
                if len(data) == 0:
                    logger.warn(f"Process '{process}' doesn't have monitor data")
                    continue
                result.append((process, self.x_axes(data), self.y_axes(), data))
        return result


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


class aTopSystem_DataUnit(db.services.DataUnit):
    def __init__(self, table, host_id, *lines, **kwargs):
        super().__init__(table, **kwargs)
        self._lines = lines
        self._host_id = host_id

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
                logger.error(f"aTop parse error: {e}")
            except Exception as e:
                f, l = get_error_info()
                logger.error("aTop unknown parse error: {}; File: {}:{}\n{}".format(e, f, l, line))
                raise
        return res

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        self._data = self._generate_atop_system_level('\n'.join(self._lines), self.table.template, self._host_id, None)
        return super().__call__(**updates)


class aTopProcesses_Debian_DataUnit(db.services.DataUnit):
    def __init__(self, table, host_id, *lines, **kwargs):
        super().__init__(table, **kwargs)
        self._lines = lines
        self._host_id = host_id
        self._processes_id = kwargs.get('processes_id', {})

    @staticmethod
    def _line_to_cells(line):
        return [c for c in re.split(r'\s+', line) if c != '']

    def is_process_monitored(self, process):
        for proc_name in ProcessMonitorRegistry()[self._processes_id].keys():
            if proc_name in process:
                return True
        return False

    @staticmethod
    def _normalise_process_name(pattern: str, replacement='.'):
        replaces = [r'/', '\\']
        for r in replaces:
            pattern = pattern.replace(r, replacement)
        return pattern

    def _filter_controlled_processes(self, *process_lines):
        for line in process_lines:
            cells = self._line_to_cells(line)
            if not self.is_process_monitored(cells[-1]):
                continue
            yield cells

    def generate_atop_process_level(self, input_text, *defaults):
        process_portion = ('PID\t' + input_text.split('PID')[1]).splitlines()

        for cells in self._filter_controlled_processes(*process_portion[1:]):
            process_name = self._normalise_process_name(f"{cells[-1]}_{cells[0]}")
            yield self.table.template(*(list(defaults) +
                                        [cells[0],
                                         timestr_to_secs(cells[1], 2),
                                         timestr_to_secs(cells[2], 2),
                                         Size(cells[3]).set_format('M').number,
                                         Size(cells[4]).set_format('M').number,
                                         Size(cells[5]).set_format('M').number,
                                         Size(cells[6]).set_format('M').number,
                                         cells[-2].replace('%', ''),
                                         process_name
                                         ]
                                        )
                                      )

    def __call__(self, **updates) -> Tuple[str, Iterable[Iterable]]:
        self._data = list(
            self.generate_atop_process_level('\n'.join(self._lines), self._host_id, None)
        )
        return super().__call__(**updates)


class aTopProcesses_Fedora_DataUnit(aTopProcesses_Debian_DataUnit):
    def generate_atop_process_level(self, input_text, *defaults):
        process_portion = ('PID\t' + input_text.split('PID')[1]).splitlines()

        for cells in self._filter_controlled_processes(*process_portion[1:]):
            process_name = self._normalise_process_name(f"{cells[-1]}_{cells[0]}")
            yield self.table.template(*(list(defaults) +
                                        [cells[0],
                                         timestr_to_secs(cells[1], 2),
                                         timestr_to_secs(cells[2], 2),
                                         Size(cells[4]).set_format('M').number if cells[4] != '-' else 0,
                                         Size(cells[5]).set_format('M').number if cells[5] != '-' else 0,
                                         Size(cells[6]).set_format('M').number if cells[6] != '-' else 0,
                                         Size(cells[7]).set_format('M').number if cells[7] != '-' else 0,
                                         cells[-2].replace('%', ''),
                                         process_name
                                         ]
                                        )
                                      )


def process_data_unit_factory(os_family):
    if os_family == 'debian':
        return aTopProcesses_Debian_DataUnit
    return aTopProcesses_Fedora_DataUnit


class aTopParser(Parser):
    def __init__(self, plugin_id, **kwargs):
        self._data_unit_class = kwargs.pop('data_unit')
        Parser.__init__(self, **kwargs)
        self.id = plugin_id
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

    def __call__(self, output) -> bool:
        # table_template = self.table.template
        try:
            stdout = output.get('stdout')
            stderr = output.get('stderr')
            rc = output.get('rc')
            assert rc == 0, f"Last {self.__class__.__name__} ended with rc: {rc}\n{stderr}"
            for atop_portion in [e.strip() for e in stdout.split('ATOP') if e.strip() != '']:
                lines = atop_portion.splitlines()
                f_line = lines.pop(0)
                ts = '_'.join(re.split(r'\s+', f_line)[2:4]) + f".{datetime.now().strftime('%S')}"
                if ts not in self._ts_cache:
                    self._ts_cache.append(ts)
                    self.data_handler(aTopSystem_DataUnit(self.table['system'], self.host_id, *lines))
                    if len(ProcessMonitorRegistry()[self.id]) > 0:
                        self.data_handler(self._data_unit_class(self.table['process'], self.host_id, *lines,
                                                                processes_id=self.id))

        except Exception as e:
            f, li = get_error_info()
            logger.error(
                f"{self.__class__.__name__}: Unexpected error: {type(e).__name__}: {e}; File: {f}:{li}")
        else:
            return True
        return False


class aTop(PlugInAPI):
    OS_DATE_FORMAT = {
        'debian': '%H:%M',
        'fedora': '%Y%m%d%H%M'
    }

    def __init__(self, parameters, data_handler, *monitor_processes, **user_options):
        PlugInAPI.__init__(self, parameters, data_handler, *monitor_processes, **user_options)

        self.file = 'atop.dat'
        self.folder = '~/atop_temp'
        self._time_delta = None
        self._os_name = None
        with self.inside_host() as ssh:
            self._os_name = self._get_os_name(ssh)

        self._name = f"{self.name}-{self._os_name}"

        self.set_commands(FlowCommands.Setup,
                          SSHLibraryCommand(SSHLibrary.execute_command, 'killall -9 atop',
                                            sudo=self.sudo_expected,
                                            sudo_password=self.sudo_password_expected),
                          SSHLibraryCommand(SSHLibrary.execute_command, f'rm -rf {self.folder}', sudo=True,
                                            sudo_password=True),
                          SSHLibraryCommand(SSHLibrary.execute_command, f'mkdir -p {self.folder}',
                                            sudo=self.sudo_expected,
                                            sudo_password=self.sudo_password_expected),
                          SSHLibraryCommand(SSHLibrary.start_command,
                                            "{nohup} atop -w {folder}/{file} {interval} &".format(
                                                nohup='' if self.persistent else 'nohup',
                                                folder=self.folder,
                                                file=self.file,
                                                interval=int(self.interval)),
                                            sudo=self.sudo_expected,
                                            sudo_password=self.sudo_password_expected))

        self.set_commands(FlowCommands.Command,
                          SSHLibraryCommand(
                              SSHLibrary.execute_command,
                              f"atop -r {self.folder}/{self.file} -b `date +{self.OS_DATE_FORMAT[self.os_name]}`",
                              sudo=True, sudo_password=True, return_rc=True, return_stderr=True,
                              parser=aTopParser(self.id,
                                                host_id=self.host_id,
                                                table={
                                                    'system': self.affiliated_tables()[0],
                                                    'process': self.affiliated_tables()[1]
                                                },
                                                data_handler=self._data_handler, counter=self.iteration_counter,
                                                interval=self.parameters.interval,
                                                data_unit=process_data_unit_factory(self._os_name))))

        self.set_commands(FlowCommands.Teardown,
                          SSHLibraryCommand(SSHLibrary.execute_command, 'killall -9 atop',
                                            sudo=True, sudo_password=True))

    @property
    def os_name(self):
        return self._os_name

    def _get_os_name(self, ssh_client: SSHLibrary):
        out, err, rc = ssh_client.execute_command("cat /etc/os-release|grep -E '^ID_LIKE='|awk -F'=' '{print$2}'",
                                                  return_rc=True, return_stderr=True)
        assert rc == 0, "Cannot occur OS name"
        out = out.replace(r'"', '')

        for _os in self.OS_DATE_FORMAT.keys():
            if _os in out:
                out = _os
                break

        logger.debug(f"OS resolved: {out}")
        return out

    def upgrade_plugin(self, *args, **kwargs):
        """
        Upgrade aTop plugin: add processes for monitor during execution

        Arguments:
        - args:     process names

        Future features:
        - kwargs:   process names following boolean flag (Default: False; If True error will raise if process diappearing)
        """
        kwargs.update(**{arg: False for arg in args})
        for process, control in kwargs.items():
            if process in ProcessMonitorRegistry()[self.id]:
                logger.info(f"Process '{process}' already registered; Activating")
                ProcessMonitorRegistry().activate(self.id, process)
                continue
            ProcessMonitorRegistry().register(self.id, process, control)
        logger.info(f"Following processes added to be monitored: {', '.join([f'{k}={v}' for k, v in kwargs.items()])}")

    def downgrade_plugin(self, *args, **kwargs):
        """
        Downgrade aTop plugin: remove processes for monitor during execution

        Arguments:
        - args:     process names
        - kwargs:   kept process names only
        """
        processes_to_unregister = list(args) + list(kwargs.keys())
        for process in processes_to_unregister:
            ProcessMonitorRegistry().deactivate(self.id, process)
        logger.info(f"Following processes removed from monitor: {', '.join(processes_to_unregister)}")

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return atop_system_level(), atop_process_level()

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        return aTopProcessLevelChart(), aTopSystemLevelChart('CPU'), aTopSystemLevelChart('CPL', 'MEM', 'PRC', 'PAG'), \
               aTopSystemLevelChart('LVM'), aTopSystemLevelChart('DSK', 'SWP'), aTopSystemLevelChart('NET')


# TODO: Add trace process flag allow error raising or collecting during monitoring if monitored processes disappearing
#  from process list


__all__ = [
    aTop.__name__,
    __doc__
]
