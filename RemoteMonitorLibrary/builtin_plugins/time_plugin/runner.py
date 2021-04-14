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

from typing import Iterable

from SSHLibrary import SSHLibrary
from robot.api import logger
from robot.utils import DotDict

from RemoteMonitorLibrary.api import plugins, model, db
from RemoteMonitorLibrary.api.tools import Logger
from .tables import TimeMeasurement, CMD_TIME_FORMAT
from .charts import TimeChart
from ...utils import get_error_info

DEFAULT_TIME_COMMAND = r'/usr/bin/time'


class TimeParser(plugins.Parser):
    def __call__(self, *outputs) -> bool:
        try:
            command_out, time_output = outputs
            data = time_output.split(',')
            row_dict = DotDict(**{k: v.replace('%', '') for (k, v) in [entry.split(':', 1) for entry in data]})
            Logger().info(f"Command: {row_dict.get('Command')} [Rc: {row_dict.get('Rc')}]")
            Logger().debug(f"Command: {row_dict.get('Command')} output:\n{command_out}")

            if self.options.get('Command', None):
                row_dict.update({'Command': self.options.get('Command')})
            data_ref = db.OutputCache().cache_output(command_out)

            row_dict.update({'Output': data_ref})
            row = self.table.template(self.host_id, None, *row_dict.values())
            self.data_handler(model.DataUnit(self.table, row))
            return True
        except Exception as e:
            f, li = get_error_info()
            Logger().error(f"{self.__class__.__name__} -> {type(e).__name__}: {e}; File: {f}:{li}\n{time_output}")


class Time(plugins.PlugInAPI):
    def __init__(self, parameters, data_handler, **options):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, **options)
        self._prefix = f"{self.__class__.__name__}_item:"
        self._format = ','.join([f"{name}:%{item}" for name, item in CMD_TIME_FORMAT.items()])
        self._time_cmd = options.get('time_cmd', DEFAULT_TIME_COMMAND)
        self._command = options.get('command', None)
        self._command_name = options.get('name', None)
        self._noise_cmd_sudo = options.get('sudo', False)
        self._noise_cmd_sudo_password = options.get('password', False)
        self._start_folder = options.get('start_folder', None)
        assert self._command, "Command not provided"

    @property
    def get_full_command(self):
        return "{start}{time_cmd} -f \"{format}\" {command}".format(
            start=f"cd {self._start_folder};" if self._start_folder else '',
            time_cmd=self._time_cmd,
            format=self._format,
            command=self._command
        )

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return TimeMeasurement(),

    @staticmethod
    def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
        base_table = TimeMeasurement()
        return tuple(TimeChart(base_table, name, *[c.name for c in base_table.fields if c.name.startswith(name)])
                     for name in ('Time', 'Memory', 'IO'))

    @property
    def periodic_commands(self) -> plugins.CommandSet_Type:
        return plugins.Command(SSHLibrary.execute_command, self.get_full_command, sudo=self._noise_cmd_sudo,
                               sudo_password=self._noise_cmd_sudo_password, return_stderr=True,
                               parser=TimeParser(host_id=self.host_id,
                                                 table=self.affiliated_tables()[0],
                                                 data_handler=self.data_handler, Command=self.name)),

    def start(self):
        super().start()
        logger.info(f"PlugIn {self.__class__.__name__} start command '{self._command}' as [{self.name}]",
                    also_console=True)
