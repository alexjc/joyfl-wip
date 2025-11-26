## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import re

from joyfl.errors import JoyValueError


def op_format(values: list, template: str) -> str:
    values = [str(v) for v in values]
    # Validate template only contains legal tokens: %<digits>, %% or non-% chars
    if not re.fullmatch(r'(?:%(\d+)|%%|[^%])+', template):
        raise JoyValueError("Invalid placeholder after '%' (expected digits or '%%').")
    # Range-check numeric placeholders
    for m in re.finditer(r'%(\d+)', template):
        idx = int(m.group(1))
        if idx < 1 or idx > len(values):
            raise JoyValueError(f"Placeholder %{idx} out of range for {len(values)} values.")
    # Translate: first numeric placeholders, then literal percents escape codes.
    fmt = re.sub(r'%(\d+)', lambda m: '{%d}' % (int(m.group(1)) - 1), template)
    fmt = fmt.replace('%%', '%')
    try:
        return fmt.format(*values)
    except Exception as e:
        raise JoyValueError(f"Invalid format string: {e}")


__joy_operators__ = [ op_format ]

if os.environ.get('JOY_DEBUG'): print('LOADED libs/_txt.py')
