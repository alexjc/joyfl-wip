## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Literal
from collections import namedtuple
from dataclasses import dataclass

class stack_list(list): pass


# Stack type is a namedtuple to save memory, yet provide tail/head accessors.
class Stack(namedtuple('Stack', ['tail', 'head'])):
    __slots__ = ()
    _nil_singleton = None

    def __new__(cls, tail, head):
        if tail is None and head is None:
            # Only one singleton creation is allowed, and it's the one just below.
            if cls._nil_singleton is None:
                self = super(Stack, cls).__new__(cls, tail, head)
                cls._nil_singleton = self
                return self
            # By convention, all other code should use `nil` explicitly.
            raise ValueError("Use the canonical `nil` instance for empty stacks")
        return super(Stack, cls).__new__(cls, tail, head)

    def __repr__(self):
        if self is nil:
            return "< nil >"
        assert self != nil

        items = []
        current = self
        while current is not nil:
            items.append(repr(current.head))
            current = current.tail
        return "< " + " ".join(reversed(items)) + " >"

    def __bool__(self):
        raise TypeError("Stack truth value is ambiguous; compare with `is nil` or `is not nil`.")

    def pushed(self, *items):
        """Push items in order of tail (left) to head (right) onto new Stack and return."""
        stack = self
        for it in items:
            stack = Stack(stack, it)
        return stack

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


Visibility = Literal["public", "private", "local"]


@dataclass
class Quotation:
    program: list          # list[Operation]
    meta: dict             # filename, start/finish, signature, etc.
    visibility: Visibility # "public", "private", or temporary "local"
    module: str | None     # MODULE name, or None for global/legacy


@dataclass(frozen=True)
class StructMeta:
    """Metadata for product-type structs registered from Joy TYPEDEF declarations."""
    name: bytes
    arity: int
    fields: tuple[dict, ...]


@dataclass(frozen=True)
class StructInstance:
    """Runtime representation of a product type instance constructed via `struct`."""
    typename: bytes              # Symbol name as emitted by `'MyStructType` literals.
    fields: tuple[object, ...]   # Field values in left-to-right declaration order.
