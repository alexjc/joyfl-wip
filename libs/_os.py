## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import glob

from joyfl import api as J


def op_list_files_b(pattern: str) -> list[str]:
    # If a directory is provided, list all `.joy` files directly inside it.
    if os.path.isdir(pattern):
        joy_pattern = os.path.join(pattern, '*.joy')
        return sorted(glob.glob(joy_pattern))

    # Otherwise, treat the argument as a glob pattern that works recursively.
    return sorted(glob.glob(pattern, recursive=True))


def op_exec_file_b(filename: str) -> object:
    try:
        res = J.run(open(filename, 'r').read(), filename=filename)
    except J.JoyError as exc:
        # Raise a new exception, currently disconnected from the original one
        # so information is lost; errors not as informative as they could be.
        raise J.JoyRuntimeError(f"os.exec-file! failed while executing `{filename}`: {exc}",
                                joy_token="os.exec-file!", joy_meta=exc.joy_meta)
    return res[-1]


__operators__ = [ op_list_files_b, op_exec_file_b ]

if os.environ.get('JOY_DEBUG'): print('LOADED libs/_os.py')
