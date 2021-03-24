from system_trace.utils.configuration import Configuration


class plugin_abstract:
    def __init__(self, name, configuration: Configuration):
        self._name = name
        self._configuration = configuration

    @property
    def name(self):
        return self._name

    @property
    def configuration(self):
        return self._configuration

    def __hash__(self):
        return hash(f"{self.__class__.__name__}_{self.name}")
