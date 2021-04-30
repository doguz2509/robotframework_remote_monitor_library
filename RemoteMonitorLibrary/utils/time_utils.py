from datetime import datetime

from RemoteMonitorLibrary.utils.logger_helper import logger


def evaluate_duration(start_ts, expected_end_ts, alias):
    end_ts = datetime.now()
    if end_ts > expected_end_ts:
        logger.warn(
            "{}: Execution ({}) took longer then interval ({}); Recommended interval increasing up to {}s".format(
                alias,
                (end_ts - start_ts).total_seconds(),
                (expected_end_ts - start_ts).total_seconds(),
                (end_ts - start_ts).total_seconds()
            ))