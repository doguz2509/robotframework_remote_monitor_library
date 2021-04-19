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
from .charts import TimeChart
from .tables import TimeMeasurement, CMD_TIME_FORMAT
from ...utils import get_error_info

DEFAULT_TIME_COMMAND = r'/usr/bin/time'


class TimeParser(plugins.Parser):
    def __call__(self, outputs) -> bool:
        command_out = outputs.get('stdout')
        time_output = outputs.get('stderr')
        rc = outputs.get('rc')
        try:

            assert rc == 0, f"Result return rc {rc}"
            data = time_output.split(',')
            row_dict = DotDict(**{k: v.replace('%', '') for (k, v) in [entry.split(':', 1) for entry in data]})
            Logger().info(f"Command: {row_dict.get('Command')} [Rc: {row_dict.get('Rc')}]")
            Logger().debug(f"Command: {row_dict.get('Command')} output:\n{command_out}")

            if self.options.get('Command', None):
                row_dict.update({'Command': self.options.get('Command')})

            row = self.table.template(self.host_id, None, *row_dict.values())
            du = model.DataUnit(self.table, row)
            self.data_handler(du)
            return True
        except Exception as e:
            f, li = get_error_info()
            raise type(e)(f"{self.__class__.__name__} ->  {e}; File: {f}:{li}")


class TimeSSHCommand(plugins.SSHLibraryCommand):
    def __init__(self, method, command, **user_options):
        self._time_cmd = user_options.pop('time_cmd', DEFAULT_TIME_COMMAND)
        self._format = ','.join([f"{name}:%{item}" for name, item in CMD_TIME_FORMAT.items()])
        super().__init__(method, command=f'{self._time_cmd} -f "{self._format}" {command} > /dev/null', **user_options)


class Time(plugins.PlugInAPI):
    def __init__(self, parameters, data_handler, **options):
        plugins.PlugInAPI.__init__(self, parameters, data_handler, **options)
        self._prefix = f"{self.__class__.__name__}_item:"

        self._time_cmd = options.get('time_cmd', DEFAULT_TIME_COMMAND)
        self._command = options.get('command', None)
        self._command_name = options.get('name', None)
        self._start_in_folder = options.get('start_in_folder', None)
        assert self._command, "SSHLibraryCommand not provided"

    @staticmethod
    def affiliated_tables() -> Iterable[model.Table]:
        return TimeMeasurement(),
        # LinesCache(), LinesCacheMap()

    @staticmethod
    def affiliated_charts() -> Iterable[plugins.ChartAbstract]:
        base_table = TimeMeasurement()
        return tuple(TimeChart(base_table, name, *[c.name for c in base_table.fields if c.name.startswith(name)])
                     for name in ('Time', 'Memory', 'IO'))

    @property
    def periodic_commands(self):
        return TimeSSHCommand(SSHLibrary.execute_command, self._command,
                              parser=TimeParser(host_id=self.host_id,
                                                table=self.affiliated_tables()[0],
                                                data_handler=self.data_handler, Command=self.name),
                              return_stderr=True, return_rc=True, start_in_folder=self._start_in_folder),

    def start(self):
        super().start()
        logger.info(f"PlugIn {self.__class__.__name__} start command '{self._command}' as [{self.name}]",
                    also_console=True)


def cache_output(output: str):
    effective_output_ref = None
    new_reference_set_required = False
    lines_ref = []
    for line_id, line in enumerate(output.splitlines()):
        try:
            effective_output_ref, line_ref = db.DataHandlerService().execute(
                f"""SELECT OUTPUT_REF, LINE_REF
                    FROM LinesCacheMap 
                    JOIN LinesCache ON LinesCache.LINE_ID = LinesCacheMap.LINE_REF
                    WHERE LinesCache.Line = '{line}' """)[0]
            Logger().debug(f"Line '{line}' already exists; refer to OUTPUT_REF = {effective_output_ref}")
        except IndexError:
            try:
                if not new_reference_set_required:
                    output_ref = db.DataHandlerService().execute(
                        db.TableSchemaService().tables.LinesCacheMap.queries.last_output_id.sql)
                    effective_output_ref = output_ref[0][0] + 1 if output_ref != [(None,)] else 0
                    Logger().debug(
                        f"Line '{line}' is new; refer to new OUTPUT_REF = {effective_output_ref}\n\tInsert line '{line}' ")
                db.DataHandlerService().execute(db.insert_sql('LinesCache', ['LINE_ID', 'Line']), *(None, line))
                line_ref = db.DataHandlerService().get_last_row_id
                new_reference_set_required = True
            except Exception as e:
                f, li = get_error_info()
                raise type(e)(f"{e}; File: {f}:{li}")

        if new_reference_set_required:
            lines_ref.append((effective_output_ref, line_id, line_ref))

    if new_reference_set_required:
        db.DataHandlerService().execute(db.insert_sql('LinesCacheMap', ['OUTPUT_REF', 'ORDER_ID', 'LINE_REF']),
                                        lines_ref)

    return effective_output_ref
