import re

_DELIMITER = ''


def add_underscore(match_obj):
    return f" {match_obj.group(0)}"


def to_title(name):
    return f"{re.sub(r'[A-Z]', add_underscore, name)}"[1:]

