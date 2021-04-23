import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from RemoteMonitorLibrary.api import db
from RemoteMonitorLibrary.api.db import TableSchemaService
from RemoteMonitorLibrary.library.robotframework_portal_addon import upload_file_to_portal
from RemoteMonitorLibrary.model.host_registry_model import HostModule, HostRegistryCache
from RemoteMonitorLibrary.runner.chart_generator import generate_charts
from RemoteMonitorLibrary.runner.html_writer import create_html
from RemoteMonitorLibrary.utils.sql_engine import DB_DATETIME_FORMAT


def _get_period_marks(period, module_id):
    start = db.DataHandlerService().execute(
        TableSchemaService().tables.Points.queries.select_state('Start', module_id, period))
    start = None if start == [] else start[0][0]
    end = db.DataHandlerService().execute(
        TableSchemaService().tables.Points.queries.select_state('End', module_id, period))
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
    def _create_chart_title(period, plugin, alias, **options):
        _str = '_'.join([name for name in [period, plugin, alias] + [f"{n}-{v}" for n, v in options.items()]
                               if name is not None])
        return re.sub(r'\s+|@|:', '_', _str).replace('__', '_')

    @keyword("Generate Module Statistics")
    def generate_module_statistics(self, period=None, plugin=None, alias=None, **options):
        """
        Generate Chart for present monitor data in visual style

        Arguments:
        - period:
        - plugin:
        - alias:
        - options:
        :Return - html link to chart file
        """
        if not os.path.exists(self._image_path):
            os.makedirs(self._image_path, exist_ok=True)

        module: HostModule = HostRegistryCache().get_connection(alias)
        chart_plugins = module.get_plugin(plugin, **options)
        chart_title = self._create_chart_title(period, plugin, f"{module}", **options)
        marks = _get_period_marks(period, module.host_id) if period else {}

        body_data = []
        for plugin in chart_plugins:
            for chart in plugin.affiliated_charts():
                try:
                    sql_query = chart.compose_sql_query(host_name=plugin.host_alias, **marks)
                    logger.debug("{}{}\n{}".format(plugin.type, f'_{period}' if period is not None else '', sql_query))
                    sql_data = db.DataHandlerService().execute(sql_query)
                    for picture_name, file_path in generate_charts(chart, sql_data, self._image_path, prefix=chart_title):
                        relative_image_path = os.path.relpath(file_path, os.path.normpath(
                            os.path.join(self._output_dir, self._log_path)))
                        body_data.append((picture_name, relative_image_path))
                        upload_file_to_portal(picture_name, file_path)
                except Exception as e:
                    logger.error(f"Error: {e}")

        html_link_path = create_html(self._output_dir, self._log_path, chart_title, *body_data)
        html_link_text = f"Chart for <a href=\"{html_link_path}\">'{chart_title}'</a>"
        logger.warn(html_link_text, html=True)
        return html_link_text
