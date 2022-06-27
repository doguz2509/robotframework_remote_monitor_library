import os
import re
from copy import deepcopy
from datetime import datetime

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from RemoteMonitorLibrary.utils.logger_helper import logger

from RemoteMonitorLibrary.api import services
from RemoteMonitorLibrary.library.robotframework_portal_addon import upload_file_to_portal

from RemoteMonitorLibrary.runner.chart_generator import generate_charts
from RemoteMonitorLibrary.plugins_modules import SSH
from RemoteMonitorLibrary.runner import HostRegistryCache
from RemoteMonitorLibrary.runner.html_writer import create_html
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT


def _get_period_marks(period, module_id):
    points = services.TableSchemaService().tables.Points
    start = services.DataHandlerService().execute(
        points.queries.select_state('Start', module_id, period))
    start = None if start == [] else start[0][0]
    end = services.DataHandlerService().execute(
        points.queries.select_state('End', module_id, period))
    end = datetime.now().strftime(DB_DATETIME_FORMAT) if end == [] else end[0][0]
    return dict(start_mark=start, end_mark=end)


class BIKeywords:
    __doc__ = """=== Statistics, measurement, analise keywords ===
    `Generate Module Statistics`
    
    Evaluate statistic trend - TBD
    """

    def __init__(self, rel_log_path, images='images'):
        try:
            self._output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        except RobotNotRunningError:
            self._output_dir = os.getcwd()
        self._log_path = rel_log_path
        self._images = images
        self._image_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, self._images))

    def get_keyword_names(self):
        return [self.generate_module_statistics.__name__]

    @staticmethod
    def _create_chart_title(*args, **options):
        list_ = [name for name in args if name]
        list_.extend([f"{n}-{v}" for n, v in options.items()])
        _str = '_'.join(list_)
        return re.sub(r'\s+|@|:', '_', _str).replace('__', '_')

    @keyword("Generate Module Statistics")
    def generate_module_statistics(self, period=None, plugin_name=None, alias=None, **options):
        """
        Generate Chart for present monitor data in visual style

        Arguments:
        - period:
        - plugin:
        - alias:
        - options:
        :Return - html link to chart file

        Note: In case report portal used chart files will be uploaded into lunch report (See in `Report Portal integration`)
        """
        if not os.path.exists(self._image_path):
            os.makedirs(self._image_path, exist_ok=True)

        modules = (HostRegistryCache().get_connection(alias), ) if alias else HostRegistryCache().get_all_connections()
        for module in modules:
            chart_plugins = module.get_plugin(plugin_name, **options)

            body_data = []
            for plugin in chart_plugins:
                body_section = []
                for chart in plugin.affiliated_charts():
                    chart_title = plugin.name
                    # if 'name' not in options.keys():
                    #     chart_title = self._create_chart_title(period, plugin_name, f"{module}", **options)
                    # else:
                    #     chart_title = options.get('name')
                    marks = _get_period_marks(period, module.host_id) if period else {}
                    marks.update(**plugin.kwargs_info)

                    try:
                        sql_query = chart.compose_sql_query(host_name=plugin.host_alias, **marks)
                        logger.debug(
                            "{}{}\n{}".format(plugin.type, f'_{period}' if period is not None else '', sql_query))
                        sql_data = services.DataHandlerService().execute(sql_query)
                        for picture_name, file_path in generate_charts(chart, sql_data, self._image_path,
                                                                       prefix=chart_title):
                            relative_image_path = os.path.relpath(file_path, os.path.normpath(
                                os.path.join(self._output_dir, self._log_path)))
                    except Exception as e:
                        logger.error(f"Error: {e}")
                    else:
                        body_section.append((picture_name, relative_image_path))
                        upload_file_to_portal(picture_name, file_path)
                body_data.append((chart_title, body_section))

            html_link_path = create_html(self._output_dir, self._log_path, chart_title, body_data)
            html_link_text = f"Chart for <a href=\"{html_link_path}\">'{chart_title}'</a>"
            logger.warn(html_link_text, html=True)
            return html_link_text
