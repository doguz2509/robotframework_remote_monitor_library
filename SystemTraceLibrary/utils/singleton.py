class Singleton:
    _instances = {}

    def __init__(self, class_):
        self._class_ = class_

    def __call__(self, *args, **kwargs):
        if self._class_ not in self._instances:
            self._instances[self._class_] = self._class_(*args, **kwargs)
        return self._instances[self._class_]
