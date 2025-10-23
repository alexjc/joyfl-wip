## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from collections import namedtuple

class stack_list(list): pass


# Stack type is a namedtuple to save memory, yet provide tail/head accessors.
Stack = namedtuple('Stack', ['tail', 'head'])

# All checks for empty stack must be done by comparing to this.
nil = Stack(None, None)


class Operation:
    FUNCTION = 1
    COMBINATOR = 2
    EXECUTE = 3

    def __init__(self, type, ptr, name, meta={}):
        self.type = type
        self.ptr = ptr
        self.name = name
        self.meta = meta

    def __hash__(self):
        return hash((self.type, self.ptr, self.name))

    def __eq__(self, other):
        return isinstance(other, Operation) and self.type == other.type and self.ptr == other.ptr

    def __repr__(self):
        return f"{self.name}"
