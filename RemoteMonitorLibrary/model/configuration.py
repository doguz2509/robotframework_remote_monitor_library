from typing import Dict, AnyStr, Tuple, Any, Callable

from robot.utils import DotDict

from RemoteMonitorLibrary.utils.sys_utils import get_error_info


class Configuration:
    def __init__(self, schema: Dict[AnyStr, Tuple], **kwargs):
        self.schema = schema
        self._parameters = DotDict()
        err = []
        for attr, (mandatory, _, _, _) in self.schema.items():
            try:
                if mandatory:
                    assert attr in kwargs.keys(), f"Mandatory parameter '{attr}' missing"
                self._set_parameter(attr, kwargs.get(attr, None))
            except AssertionError as e:
                err.append(f"{e}")
            except Exception as e:
                f, l = get_error_info()
                err.append(f"Unexpected error occurred during handle parameter '{attr}'; File: {f}:{l} - Error: {e}")

        assert len(err) == 0, "Following fields errors occurred:\n\t{}".format('\n\t'.join(err))

    def _set_parameter(self, parameter, value):
        attr_template = self.schema.get(parameter, None)
        assert attr_template, f"Unknown parameter '{parameter}' provided"
        _, default, formatter, type_ = attr_template
        if type_:
            if value:
                param_value = formatter(value) if not isinstance(value, type_) else value
            else:
                param_value = default
        else:
            param_value = value
        self._parameters[parameter] = param_value

    @property
    def parameters(self):
        return self._parameters

    @property
    def alias(self):
        return self.parameters.alias

    def update(self, dict_: dict = None, **kwargs):
        dict_ = dict_ or {}
        dict_.update(**kwargs)
        unexpected = {}
        for name, value in dict_.items():
            try:
                self._set_parameter(name, value)
            except AssertionError:
                unexpected.update({name: value})
        return unexpected

    def clone(self):
        return type(self)(self.schema, **self.parameters)

