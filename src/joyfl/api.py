## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from .types import Operation
from .runtime import Runtime

nil = tuple()

_RUNTIME = Runtime()

def __getattr__(name):
    return getattr(_RUNTIME, name)
