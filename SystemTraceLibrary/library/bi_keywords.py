import os
import re
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from SystemTraceLibrary.api import db
from SystemTraceLibrary.api.db import TableSchemaService
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

    @keyword("Generate Module Statistics")
    def generate_module_statistics(self, period=None, plugin=None, alias=None):
        module: HostModule = HostRegistryCache().get_connection(alias)
        marks = _get_period_marks(period, module.host_id) if period else {}

        if not os.path.exists(self._image_path):
            os.mkdir(self._image_path)
        body = ''

        chart_plugins = {k: v for k, v in module.active_plugins.items() if plugin is None or k == plugin}

        for alias, plugin in chart_plugins.items():
            for chart in plugin.affiliated_charts():
                try:
                    sql_query = chart.compose_sql_query(host_name=plugin.thread_name, **marks)
                    logger.debug(f"{plugin.type}{f'_{period}' if period else ''}_{marks}\n{sql_query}")
                    sql_data = db.DataHandlerService().execute(sql_query)
                    for picture_name, file_path in chart.generate(sql_data, self._image_path,
                                                                  prefix=f"{plugin.type}{f'_{period}' if period else ''}"):
                        relative_image_path = os.path.relpath(file_path, os.path.normpath(
                            os.path.join(self._output_dir, self._log_path)))
                        body += HTML_IMAGE_REF.format(relative_path=relative_image_path, picture_title=picture_name)
                except Exception as e:
                    logger.error(f"Error: {e}")

        html_file_name = "{}.html".format(re.sub(r'\s+|@|:', '_', period or module.alias))
        html = HTML.format(title=period or module.alias, body=body)
        html_full_path = os.path.normpath(os.path.join(self._output_dir, self._log_path, html_file_name))
        html_link_path = '/'.join([self._log_path, html_file_name])
        with open(html_full_path, 'w') as sw:
            sw.write(html)
        logger.warn(f"<a href=\"{html_link_path}\">Session '{period or module.alias}' statistics</a>", html=True)
        return f"<a href=\"{html_link_path}\">Session '{period or module.alias}' statistics</a>"
