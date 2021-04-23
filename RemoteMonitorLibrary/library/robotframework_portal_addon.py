import os

from RemoteMonitorLibrary.utils import Logger

__doc__ = """ === agent-PortalRobotframework === 

    Add to CLI
    
     --listener
     robotframework_reportportal.listener
     --variable
     RP_UUID:077ee5d9-b6ad-47c7-9a5c-9f29a6826a25
     --variable
     RP_ENDPOINT:http://192.168.25.5:8080
     --variable
     RP_LAUNCH:RemoteMonitor
     --variable
     RP_PROJECT:dmitry_oguz_personal
     --variable
     ENV:TIRAMISU
     --variable
     PLATFORM:CUSTOM_REMOTE_CHROME
     --variable
     x_api_version:1.4.0
     
     """

try:
    from robotframework_reportportal import logger as portal_logger
    from robotframework_reportportal.exception import RobotServiceException
    PORTAL = True
    Logger().info(f"RobotFramework portal available")
except (ImportError, ValueError):
    Logger().warning(f"RobotFramework portal not available")
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
