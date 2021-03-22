from robot.utils.connectioncache import ConnectionCache

from system_trace.utils import Singleton


@Singleton
class Tracing(ConnectionCache):
    pass

