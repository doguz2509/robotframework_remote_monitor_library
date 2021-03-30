from SSHLibrary.sshconnectioncache import SSHConnectionCache

from system_trace.utils import Singleton


@Singleton
class TraceConnectionCache(SSHConnectionCache):
    def __init__(self):
        SSHConnectionCache.__init__(self)

    @property
    def name_cache(self):
        return [session.session_id for session in self.connections]
