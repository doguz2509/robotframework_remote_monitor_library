import os

from RemoteMonitorLibrary.utils import Logger

try:
    from robotframework_reportportal import logger as portal_logger
    from robotframework_reportportal.exception import RobotServiceException
    PORTAL = True
    Logger().info(f"RobotFramework portal available")
except (ImportError, ValueError):
    Logger().warn(f"RobotFramework portal not available")
    PORTAL = False


def upload_file_to_portal(link_title, file_path):
    if not PORTAL:
        return

    try:
        _, file_name = os.path.split(file_path)
        with open(file_path, 'rb') as file_reader:
            file_data = file_reader.read()
        portal_logger.info(link_title, attachment={
            'name': file_name,
            'data': file_data,
            'mime': 'image/png'
        })
        return True
    except RobotServiceException as e:
        Logger().error(f"Cannot upload file '{file_path}'; Reason: {e}")
    except Exception as e:
        Logger().error(f"Unexpected error during upload file '{file_path}'; Reason: {e}")
    return False
