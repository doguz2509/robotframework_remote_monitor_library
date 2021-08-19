__doc__ = """# first time setup CentOS - for Ubuntu/Debian and others see https://www.cyberciti.biz/tips/compiling-linux-kernel-26.html 
curl  https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.11.10.tar.xz -o kernel.tar.xz
unxz kernel.tar.xz
tar xvf kernel.tar
cd linux-5.11.10/
cp -v /boot/config-$(uname -r) .config
sudo dnf -y group install  "Development Tools"
sudo dnf -y install time ncurses-devel hmaccalc zlib-devel binutils-devel elfutils-libelf-devel bison flex openssl-devel make gcc 
make defconfig
/usr/bin/time -f "$(date +'%Y-%m-%dT%H:%M:%S%:z'):\t%e real,\t%U user,\t%S sys,\t%M max_mem_kb,\t%F page_faults,\t%c involuntarily_ctx_swtc,\t%I file_inputs,\t%O file_outputs,\t%r socket_recieved,\t%s socket_sent" -a -o data.txt  make -j 4 clean all
and you'll know something is happening when you start to see real compilation happening... by looking at the data.txt and seeing something like the following 
2021-03-25T18:58:43+02:00:	679.22 real,	1082.81 user,	160.85 sys,	248824 max_mem_kb,	4 page_faults,	120697 involuntarily_ctx_swtc,	98104 file_inputs,	1492752 file_outputs,	0 socket_recieved,	0 socket_sent
#BTW the above was without mlp ... so let's make sure we run at least 10 samples without mlp and 10 samples after - to conclude on avg, max and min for without mlp and then for with mlp """

import os
import re
from typing import Iterable, Any, Tuple

from SSHLibrary import SSHLibrary
from robot.utils import DotDict

from RemoteMonitorLibrary.api import model
from RemoteMonitorLibrary.api.plugins import *
from RemoteMonitorLibrary.runner.ssh_module import SSHHostModule
from RemoteMonitorLibrary.utils import logger

__doc__ = """
== Time plugin overview ==
    Wrap linux /usr/bin/time utility for periodical execution and monitor of customer command for process io, memory, cpu, etc

    Full documentation for time utility available on [https://linux.die.net/man/1/time|time man(1)]

    === Plugin parameters ===

    Parameters can be supplied via keyword `Start monitor plugin` as key-value pairs

    Time plugin arguments:

    - command: str -> command to be executed and measured by time (Mandatory)
    
    | Note: Pay attention not to redirect command stderr to stdout (avoid '2>&1'); 
    | Time write to stderr by itself and it send to parser

    - name: User friendly alias for command (Optional)
    - start_in_folder: path to executable binary/script if execution by path not relevant (Optional)
    - return_stdout: bool -> if true output store to cache in DB
    - sudo: True if sudo required, False if omitted (Optional)
    - sudo_password: True if password required for sudo, False if omitted (Optional)

      On plugin start sudo and sudo_password will be replace with sudo password provided for connection module
    
    Examples:
    |       Flags |  What really executed |
    | <command> | /usr/bin/time -f "..." 'command' > /dev/null |
    | <command> start_in_folder=<folder> | cd <folder> ; /usr/bin/time -f "..." command > /dev/null |
    | <command> start_in_folder=<folder> return_stdout=yes |  cd <folder> ;/usr/bin/time -f "..." command |
    | <command> start_in_folder=<folder> return_stdout=yes sudo=yes |  cd <folder> ;sudo /usr/bin/time -f "..." command |
    
"""

from RemoteMonitorLibrary.model.errors import RunnerError

from RemoteMonitorLibrary.utils import get_error_info
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT

DEFAULT_TIME_COMMAND = r'/usr/bin/time'

CMD_TIME_FORMAT = DotDict(
    TimeReal="e",
    TimeKernel="S",
    TimeUser="U",
    TimeCPU="P",
    MemoryMaxResidentSize="M",
    MemoryAverage="t",
    MemoryAverageTotal="K",
    MemoryAverageProcessData="D",
    MemoryAverageProcessStack="p",
    MemoryAverageProcessShared="X",
    MemorySystemPageSize="Z",
    MemoryMajorPageFaults="F",
    MemoryMinorPageFaults="R",
    MemoryProcessSwapped="W",
    MemoryProcessContextSwitched="c",
    MemoryWait="w",
    IOInput="I",
    IOOutput="O",
    IOSocketRecieved="r",
    IOSocketSent="s",
    IOSignals="k",
    Rc="x",
    Command="C"
)

TIME_BG_SCRIPT = """ 
#!/bin/bash

cd {start_folder}

while :
do
    {time_command} -f \\"TimeStamp:\\$(date +'{date_format}'),{format}\\" -o ~/time_data/{title}/.time_{title}.txt {command} > {output}
    mv ~/time_data/{title}/.time_{title}.txt ~/time_data/{title}/time_{title}.txt
    {mv_output}
    sleep {interval}
done
"""

TIME_READ_SCRIPT = """
#!/bin/bash
cat ~/time_data/{title}/time_{title}.txt >&2
{read_output}
"""

TIME_NAME_CACHE = []


class TimeMeasurement(model.PlugInTable):
    def __init__(self):
        super().__init__('TimeMeasurement')
        self.add_time_reference()
        for f in [model.Field(f, model.FieldType.Int) for f in CMD_TIME_FORMAT.keys() if f != 'Command'] + \
                 [model.Field('Command')]:
            self.add_field(f)
        self.add_output_cache_reference()


class TimeChart(ChartAbstract):
    def __init__(self, table: model.Table, title, *sections):
        self._table = table
        ChartAbstract.__init__(self, *(sections if len(sections) > 0 else self._table.columns))
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
        return [s.replace(self.title, '') for s in self.sections]

    def __str__(self):
        return f"{self.__class__.__name__}: {', '.join(self.sections)}"

    def generate_chart_data(self, query_results: Iterable[Iterable], extension=None) -> \
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


class TimeParser(Parser):
    def __call__(self, outputs, datetime=None) -> bool:
        command_out = outputs.get('stdout', None)
        time_output = outputs.get('stderr', None)
        rc = outputs.get('rc')
        try:
            exp_rc = self.options.get('rc', None)
            if exp_rc:
                if rc not in [int(_rc) for _rc in re.split(r'\s*\|\s*', exp_rc)]:
                    raise AssertionError(
                        f"Result return rc {rc} not match expected\nStdOut:\n\t{command_out}\nStdErr:\n\t{time_output}")
            data = time_output.split(',')
            row_dict = DotDict(**{k: v.replace('%', '') for (k, v) in [entry.split(':', 1) for entry in data]})
            for k in row_dict.keys():
                if k == 'Command':
                    continue
                row_dict.update({k: float(row_dict[k])})
            logger.info(f"Command: {row_dict.get('Command')} [Rc: {row_dict.get('Rc')}]")

            row = self.table.template(self.host_id, None, *tuple(list(row_dict.values()) + [-1]))
            du = model.data_factory(self.table, row, output=command_out, datetime=datetime)

            self.data_handler(du)
            return True
        except Exception as e:
            f, li = get_error_info()
            logger.error(f"{self.__class__.__name__}: {e}; File: {f}:{li}")
            raise RunnerError(f"{self}", f"{e}; File: {f}:{li}")


class TimeCachedParser(TimeParser):
    def __call__(self, outputs, datetime=None):
        time_output = outputs.get('stderr', None)
        rc = outputs.get('rc')

        if 'No such file or directory' in time_output and rc == 1:
            logger.warn(f"Time command still not completed first iteration")
            return True
        assert rc == 0, f"Error RC occur - {outputs}"
        time_stamp, time_output = time_output.split(',', 1)
        _, datetime = time_stamp.split(':', 1)
        outputs.update(**{'stderr': time_output})
        return super().__call__(outputs, datetime=datetime)


class TimeStartCommand(SSHLibraryCommand):
    def __init__(self, command, **user_options):
        self._time_cmd = user_options.pop('time_cmd', DEFAULT_TIME_COMMAND)
        self._format = ','.join([f"{name}:%{item}" for name, item in CMD_TIME_FORMAT.items()])
        self._base_cmd = command
        self._start_in_folder = user_options.pop('start_in_folder', None)
        if not user_options.get('return_stdout', False):
            self._base_cmd += ' > /dev/null'
        command = "{cd_to_folder}{time} -f \"{format}\" {base_cmd}".format(
            cd_to_folder=f'cd {self._start_in_folder}; ' if self._start_in_folder else '',
            time=self._time_cmd,
            format=self._format,
            base_cmd=self._base_cmd
        )
        super().__init__(SSHLibrary.start_command, command,
                         **extract_method_arguments(SSHLibrary.start_command.__name__, **user_options))

    def __str__(self):
        return f"{self._method.__name__.replace('_', ' ').capitalize()}:  " \
               f"{f'cd {self._start_in_folder}; ' if self._start_in_folder else ''}" \
               f"{self._time_cmd} -f \"...\" " \
               f"{', '.join([f'{a}' for a in [self._base_cmd] + [f'{k}={v}' for k, v in self._ssh_options.items()]])}" \
               f"{'; Parser: '.format(self.parser) if self.parser else ''}"


class TimeReadOutput(SSHLibraryCommand):
    def __init__(self, **user_options):
        self._format = ','.join([f"{name}:%{item}" for name, item in CMD_TIME_FORMAT.items()])
        user_options.update({'return_stderr': True, 'return_rc': True})
        super().__init__(SSHLibrary.read_command_output, parser=user_options.pop('parser', None),
                         **extract_method_arguments(SSHLibrary.read_command_output.__name__, **user_options))

    def __str__(self):
        return f"{self._method.__name__.replace('_', ' ').capitalize()}: " \
               f"{', '.join([f'{k}={v}' for k, v in self._ssh_options.items()])}" \
               f"'; Parser: {'assigned' if self.parser else 'N/A'}"


class GetPIDList(Variable):
    def __call__(self, output):
        self.result = {'pid_list': output.replace('\n', ' ')}


class Time(SSH_PlugInAPI):
    def __init__(self, parameters, data_handler, *args, **user_options):
        self._command = user_options.pop('command', None)
        user_options.update({'name': user_options.get('name', super().id)})
        self._command_name = user_options.get('name')

        assert self.id not in TIME_NAME_CACHE, f"Name '{self._command_name}' already exists"
        TIME_NAME_CACHE.append(self.id)
        user_options.update({'persistent': user_options.get('persistent', 'no')})

        SSH_PlugInAPI.__init__(self, parameters, data_handler, *args, **user_options)
        self._prefix = f"{self.__class__.__name__}_item:"

        self._time_cmd = user_options.get('time_cmd', DEFAULT_TIME_COMMAND)
        self._start_in_folder = user_options.get('start_in_folder', None)
        if self._start_in_folder:
            self._verify_folder_exist()
            self.options.update({'start_in_folder': self._start_in_folder})
        self._format = ','.join([f"{name}:%{item}" for name, item in CMD_TIME_FORMAT.items()])
        assert self._command, "SSHLibraryCommand not provided"
        self.options.update(**self.normalise_arguments(**self.options))
        if user_options.get('rc', None) is not None:
            assert user_options.get('return_rc'), "For verify RC argument 'return_rc' must be provided"

        if self.persistent:
            self.set_commands(FlowCommands.Command,
                              TimeStartCommand(self._command, **self.options),
                              TimeReadOutput(parser=TimeParser(host_id=self.host_id,
                                                               table=self.affiliated_tables()[0],
                                                               data_handler=self.data_handler, Command=self.name),
                                             **self.options))
        else:
            time_write_script = TIME_BG_SCRIPT.format(
                start_folder=f"{self._start_in_folder}" if self._start_in_folder else '',
                time_command=self._time_cmd,
                format=self._format,
                command=self._command,
                interval=int(self.parameters.interval),
                output='/dev/null',
                title=self.id,
                # FIXME: ReturnStdout disabled due to performance issues; Pending fix in next releases
                #  output='~/time_data/.temp_output.txt' if self.options.get('return_stdout', False) else '/dev/null',
                mv_output='mv ~/time_data/{t}/.temp_{t}_output.txt ~/time_data/output_{t}.txt'.format(t=self.id)
                if self.options.get('return_stdout', False) else '',
                date_format=DB_DATETIME_FORMAT
            )
            time_read_script = TIME_READ_SCRIPT.format(
                title=self.id,
                read_output='cat ~/time_data/{t}/output_{t}.txt >&1'.format(t=self.id)
                if self.options.get('return_stdout', False) else ''
            )

            pid_list = GetPIDList()

            self.set_commands(FlowCommands.Teardown,
                              SSHLibraryCommand(SSHLibrary.execute_command,
                                                "ps -ef|egrep 'time_write_{}.sh|{}'|grep -v grep|"
                                                "awk '{{{{print$2}}}}'".format(self.id, self._command),
                                                sudo=self.sudo_expected,
                                                sudo_password=self.sudo_password_expected,
                                                return_stdout=True,
                                                variable_setter=pid_list),
                              SSHLibraryCommand(SSHLibrary.execute_command, "kill -9 {pid_list}",
                                                sudo=self.sudo_expected,
                                                sudo_password=self.sudo_password_expected,
                                                variable_getter=pid_list)
                              )

            self.set_commands(FlowCommands.Setup,
                              self.teardown,
                              SSHLibraryCommand(SSHLibrary.execute_command,
                                                f"mkdir -p ~/time_data/{self.id}",
                                                return_rc=True),
                              SSHLibraryCommand(SSHLibrary.execute_command, f"rm -rf ~/time_data/{self.id}/*",
                                                sudo=self.sudo_expected,
                                                sudo_password=self.sudo_password_expected,
                                                return_rc=True,
                                                return_stderr=True),
                              SSHLibraryCommand(SSHLibrary.execute_command,
                                                f"echo \"{time_write_script}\" > ~/time_data/{self.id}/time_write_{self.id}.sh",
                                                return_rc=True, parser=ParseRC()),
                              SSHLibraryCommand(SSHLibrary.execute_command,
                                                f"echo \"{time_read_script}\" > ~/time_data/{self.id}/time_read_{self.id}.sh",
                                                return_rc=True, parser=ParseRC()),
                              SSHLibraryCommand(SSHLibrary.execute_command,
                                                f'chmod +x ~/time_data/{self.id}/*.sh',
                                                return_rc=True, parser=ParseRC()),
                              SSHLibraryCommand(SSHLibrary.start_command,
                                                f'nohup ~/time_data/{self.id}/time_write_{self.id}.sh &')
                              )

            self.set_commands(FlowCommands.Command,
                              SSHLibraryCommand(SSHLibrary.execute_command, f'~/time_data/{self.id}/time_read_{self.id}.sh',
                                                sudo=self.sudo_expected,
                                                sudo_password=self.sudo_expected,
                                                return_stderr=True,
                                                return_rc=True,
                                                parser=TimeCachedParser(host_id=self.host_id,
                                                                        table=self.affiliated_tables()[0],
                                                                        data_handler=self.data_handler,
                                                                        Command=self.name)))

    @property
    def id(self):
        return f"{self.__class__.__name__}_{self._command_name}"

    def _verify_folder_exist(self):
        with self.on_connection() as ssh:
            if self._start_in_folder.startswith('~'):
                _path = self._start_in_folder
                user_home = ssh.execute_command('echo $HOME').strip()
                _path = _path.replace('~', user_home)
                logger.info(f"Expand folder {self._start_in_folder} to {_path}")
                self._start_in_folder = _path
            ssh.directory_should_exist(os.path.expanduser(self._start_in_folder))

    @staticmethod
    def affiliated_modules():
        return SSHHostModule

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return TimeMeasurement(),

    @staticmethod
    def affiliated_charts() -> Iterable[ChartAbstract]:
        base_table = TimeMeasurement()
        return tuple(TimeChart(base_table, name, *[c.name for c in base_table.fields if c.name.startswith(name)])
                     for name in ('Time', 'Memory', 'IO'))


__all__ = [
    Time.__name__,
    __doc__
]
