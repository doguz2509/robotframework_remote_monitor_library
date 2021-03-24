from abc import ABC

from .model import parser_addon_abstract, _data_handler_addon_abstract
from .model.plugin_abstract import plugin_abstract
from .model.ssh_addon import SSH_MODES, ssh_non_interactive_plugin, ssh_interactive_plugin


class InteractivePlugIn(plugin_abstract, ssh_interactive_plugin, parser_addon_abstract,
                        _data_handler_addon_abstract, ABC):
    pass


class NonInteractivePlugIn(plugin_abstract, ssh_non_interactive_plugin, parser_addon_abstract,
                           _data_handler_addon_abstract, ABC):
    pass


def plugin_factory(mode: SSH_MODES):
    if mode == SSH_MODES.Interactive:
        return InteractivePlugIn
    elif mode == SSH_MODES.NonInteractive:
        return NonInteractivePlugIn
    raise TypeError(f"Unknown ssh mode '{mode}'")


__all__ = [
    'SSH_MODES',
    'plugin_factory',
    'InteractivePlugIn',
    'NonInteractivePlugIn'
]
