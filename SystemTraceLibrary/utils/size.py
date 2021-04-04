
import enum
import operator
import re

from robot.api import logger


def get_minimal(type_):
    return min([type_[i] for i in type_.__dict__ if not i.startswith('_')])


class _SizeFormat(enum.IntEnum):
    b = 1
    B = 8
    k = 1000
    K = 1000 * 8
    m = 1000000
    M = 1000000 * 8
    g = 1000000000
    G = 1000000000 * 8


BITRATE_REGEX = re.compile(r'([\d.]+)(.*)')


class Size(type):

    def __new__(mcs, bitrate_input: str = None, **kwargs):
        return super().__new__(mcs, 'Size', (object,), kwargs)

    def __init__(cls, bitrate_input: str = None, **kwargs):
        super().__init__('Size')
        cls.__rate = kwargs.get('rate', _SizeFormat)
        cls.__start_from = get_minimal(cls.__rate)
        cls.__after_coma: int
        cls.__str_format: str

        if bitrate_input is None:
            cls.__number: float = float(kwargs.get('number', -1))
            cls.__format_number()
            cls.__format = kwargs.get('format', cls.__start_from.name)
        else:
            cls.__parse(bitrate_input)

        if cls.__number == -1:
            raise ValueError("Cannot create PacketSize instance")

        cls.__bit_value = cls.__number * cls.__format.value

    def __format__(self, format_spec):
        old_format = self.__str_format
        try:
            if format_spec != '':
                self.__str_format = "{{:{new_format}}}{{}}".format(new_format=format_spec)
            return str(self)
        except Exception as e:
            logger.error(e)
        finally:
            self.__str_format = old_format

    def __str__(self):
        return self.__str_format.format(self.number, self.format)

    def __repr__(self):
        return str(self)

    def __format_number(self):
        self.__after_coma = 0 if round(self.__number) == self.__number else 2
        self.__str_format = "{{:.{dig}f}}{{}}".format(dig=self.__after_coma)

    def __parse(self, bitrate_str: str):
        try:
            m = BITRATE_REGEX.match(str(bitrate_str))
            if m is None:
                raise AttributeError("Wrong bitrate format ({})".format(bitrate_str))
            self.__number = float(m.groups()[0])
            self.__format_number()
            self.set_format(m.groups()[1])
        except Exception as e:
            logger.error("Cannot parse PacketSize value string '{}' with error: {}".format(bitrate_str, e))
            raise e

    @property
    def bit_value(self):
        return self.__bit_value

    @property
    def number(self):
        return self.__bit_value / self.__format.value

    def print(self, f=None):
        pattern = re.compile(r'(\d+)(.(\d+))?')
        if f is not None:
            _format = _SizeFormat[f]
        else:
            _format = self._get_optimal_format()

        return "{}{}".format(self.__bit_value / _format.value, _format.name)

    def _get_optimal_format(self):
        pattern = re.compile(r'(\d+)(.([\de\-g]+))?')
        for _f in _SizeFormat:
            example = self.print(_f.name)
            try:
                _, bc, _, ac, b = pattern.split(example)
                ac_int = int(str(ac))
                bc_len = len(str(bc))
                ac_len = len(str(ac_int))
                if b == b.upper() and bc_len > ac_len:
                    return _SizeFormat[b]
            except Exception as e:
                print(e)

        return _SizeFormat.K

    @property
    def format(self):
        return self.__format.name

    def set_format(self, value):
        self.__format = _SizeFormat[value] if value != '' else _SizeFormat.b
        return self

    def _compare_operation(self, other, operation: operator):
        if isinstance(other, Size):
            return operation(self.bit_value, other.bit_value)
        elif isinstance(other, (int, float)):
            return operation(self.number, other)

        raise ValueError("Argument '{}' not match operation {}".format(other, operation))

    def _execute_operation(self, other, operation: operator):
        if isinstance(other, Size):
            result_format = _SizeFormat[self.format] \
                    if _SizeFormat[self.format].value > _SizeFormat[other.format].value \
                    else _SizeFormat[other.format]
            result_number = operation(self.bit_value, other.bit_value) / result_format.value
        elif isinstance(other, (int, float)):
            result_format = _SizeFormat[self.format]
            result_number = operation(self.bit_value, other) / result_format.value
        else:
            raise ValueError("Argument '{}' not match operation {}".format(other, operation))

        return Size(number=result_number, format=result_format.name)

    def __eq__(self, other):
        return self._compare_operation(other, operator.eq)

    def __ne__(self, other):
        return self._compare_operation(other, operator.ne)

    def __gt__(self, other):
        return self._compare_operation(other, operator.gt)

    def __ge__(self, other):
        return self._compare_operation(other, operator.ge)

    def __lt__(self, other):
        return self._compare_operation(other, operator.lt)

    def __le__(self, other):
        return self._compare_operation(other, operator.le)

    def __add__(self, other):
        return self._execute_operation(other, operator.add)

    def __sub__(self, other):
        return self._execute_operation(other, operator.sub)

    def __mul__(self, other):
        return self._execute_operation(other, operator.mul)

    def __truediv__(self, other):
        return self._execute_operation(other, operator.truediv)

    @staticmethod
    def sum(*packet_list, **kwargs):
        _list = list(packet_list)
        if _list.__len__() == 0:
            return Size(number=0, **kwargs)
        _res = Size(_list.pop())
        while _list.__len__() > 0:
            _next = _list.pop()
            _next.format = _res.format
            _res += Size(_next, **kwargs)
        return _res

    @staticmethod
    def min(*packet_list, **kwargs):
        _list = list(packet_list)
        if _list.__len__() == 0:
            return Size(number=0, **kwargs)
        _res = Size(_list.pop(), **kwargs)
        while _list.__len__() > 0:
            _next = _list.pop()
            _next.format = _res.format
            if _next < _res:
                _res = _next
        return _res

    @staticmethod
    def max(*packet_list, **kwargs):
        _list = list(packet_list)
        if _list.__len__() == 0:
            return Size(number=0, **kwargs)
        _res = Size(_list.pop(), **kwargs)
        while _list.__len__() > 0:
            _next = _list.pop()
            _next.format = _res.format
            if _next > _res:
                _res = _next
        return _res


if __name__ == '__main__':
    d = Size('1.6M')
    print(f"{d}")
