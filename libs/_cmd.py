## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import sys
from typing import Any


def _parse_args(argv: list[str]) -> dict[bytes, Any]:
    options: dict[bytes, Any] = {}
    for arg in argv:
        # Long options: --key or --key=value
        if arg.startswith('--'):
            item = arg[2:]
            if '=' in item:
                key, value = item.split('=', 1)
                options[key.encode('utf-8')] = value
            else:
                options[item.encode('utf-8')] = True
            continue
        # Short flags: -q -v etc.  Map each character to a boolean True.
        if arg.startswith('-') and len(arg) > 1:
            for ch in arg[1:]:
                options[ch.encode('utf-8')] = True

    return options


def op_options() -> dict:
    return _parse_args(sys.argv[1:])

def op_exit_b(retval: int) -> None:
    sys.exit(retval)


__operators__ = [ op_options, op_exit_b ]

if os.environ.get('JOY_DEBUG'): print('LOADED libs/_cmd.py')