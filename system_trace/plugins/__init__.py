
from .atop_plugin import aTopPlugIn
from ..model import PlugIn

SYSTEM_PLUGINS = [
    aTopPlugIn()
]


class PluginsRegistry:
    def __init__(self):
        self._registered = {}

    def register(self, plugin: PlugIn):
        assert plugin not in self._registered, f"PluIn '{plugin}' already registered"
        self._registered.update({plugin: True})

    def de_register(self, plugin_name: str):
        plug_in = [p.name for p in self._registered.keys()]
        assert len(plug_in) == 1, f"PlugIn not '{plugin_name}' registered"
        plug_in = plug_in[0]
        plug_in.stop()
        del self._registered[plug_in]


__all__ = [
    PluginsRegistry.__name__
]
