## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from .types import Operation, Stack, nil
from .errors import *
from .runtime import Runtime

_RUNTIME = Runtime()

def __getattr__(name):
    return getattr(_RUNTIME, name)
