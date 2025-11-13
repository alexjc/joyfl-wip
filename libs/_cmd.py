import sys
from typing import Any


def _parse_args(argv: list[str]) -> dict[bytes, Any]:
    options: dict[bytes, Any] = {}
    for arg in argv:
        if not arg.startswith('--'):
            continue
        item = arg[2:]
        if '=' in item:
            key, value = item.split('=', 1)
            options[key.encode('utf-8')] = value
        else:
            options[item.encode('utf-8')] = True
    return options


def op_options() -> dict:
    return _parse_args(sys.argv[1:])


__operators__ = [op_options]
