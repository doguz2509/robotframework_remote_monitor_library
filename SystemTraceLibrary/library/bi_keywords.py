import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from SystemTraceLibrary.api import db
from SystemTraceLibrary.api.db import TableSchemaService
from SystemTraceLibrary.model.chart_model import generate_charts
from SystemTraceLibrary.model.chart_model.html_template import HTML_IMAGE_REF, HTML
from SystemTraceLibrary.model.host_registry_model import HostModule, HostRegistryCache
from SystemTraceLibrary.utils.sql_engine import DB_DATETIME_FORMAT


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
    
    `Evaluate statistic trend` - TBD"""

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
    def _create_chart_title(period, plugin, alias, delimiter='_'):
        _str = delimiter.join([name for name in [period, plugin, alias] if name is not None])
        return re.sub(r'\s+|@|:|-', '_', _str).replace('__', '_')

    @keyword("Generate Module Statistics")
    def generate_module_statistics(self, period=None, plugin=None, alias=None):

        if not os.path.exists(self._image_path):
            os.mkdir(self._image_path)

        module: HostModule = HostRegistryCache().get_connection(alias)
        marks = _get_period_marks(period, module.host_id) if period else {}
        chart_plugins = {k: v for k, v in module.active_plugins.items() if plugin is None or type(v).__name__ == plugin}
        chart_title = self._create_chart_title(period, plugin, module.alias)
        body = ''

        for alias, plugin in chart_plugins.items():
            for chart in plugin.affiliated_charts():
                try:
                    sql_query = chart.compose_sql_query(host_name=plugin.thread_name, **marks)
                    logger.debug(f"{plugin.type}{f'_{period}' if period else ''}_{marks}\n{sql_query}")
                    sql_data = db.DataHandlerService().execute(sql_query)
                    # prefix = f"{plugin.type}{f'_{period}' if period else ''}"
                    for picture_name, file_path in generate_charts(chart, sql_data, self._image_path, prefix=chart_title):
                        relative_image_path = os.path.relpath(file_path, os.path.normpath(
                            os.path.join(self._output_dir, self._log_path)))
                        body += HTML_IMAGE_REF.format(relative_path=relative_image_path, picture_title=picture_name)
                except Exception as e:
                    logger.error(f"Error: {e}")

        html_file_name = "{}.html".format(chart_title)
        html = HTML.format(title=period or module.alias, body=body)
        html_full_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, html_file_name))
        html_link_path = '/'.join([self._log_path, html_file_name])
        with open(html_full_path, 'w') as sw:
            sw.write(html)
        html_link_text = f"<a href=\"{html_link_path}\">Chart for '{chart_title}'</a>"
        logger.warn(html_link_text, html=True)
        return html_link_text
