import os

from RemoteMonitorLibrary.utils.logger_helper import logger

__doc__ = """= Integrations =
    
    == Report Portal integration ==
    
    Allow reporting into central portal
    
    For enable add listener to robot command line:
    | --listener robotframework_reportportal.listener
    | --variable RP_UUID:<user token>
    | --variable RP_ENDPOINT:http://<your portal URI>:8080
    | --variable RP_LAUNCH:<Lunch name>
    | --variable RP_PROJECT:<Portal project name in lower case>
    | --variable ENV:TIRAMISU
    | --variable PLATFORM:CUSTOM_REMOTE_CHROME
    | --variable x_api_version:1.4.0
     
     For portal installation and further information look in [https://github.com/reportportal/agent-Python-RobotFramework|ReportPortal]
    
    """

try:
    from robotframework_reportportal import logger as portal_logger
    from robotframework_reportportal.exception import RobotServiceException
    PORTAL = True
    logger.info(f"RobotFramework portal available")
except (ImportError, ValueError):
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
        logger.error(f"Cannot upload file '{file_path}'; Reason: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during upload file '{file_path}'; Reason: {e}")
    return False
