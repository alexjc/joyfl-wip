## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Literal, TypeVar
from numbers import Number
from fractions import Fraction
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


TYPE_NAME_MAP: dict[str, Any] = {
    'int': int, 'integer': int, 'float': float, 'double': float,
    'bool': bool, 'boolean': bool,
    'symbol': bytes, 'sym': bytes,
    'str': str, 'string': str, 'text': str,
    'number': Number,
    'fraction': Fraction, 'fract': Fraction,
    'list': list, 'array': list, 'quot': list,
    'stack': Stack,
    'any': Any, '': Any,
}


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
    program: list                 # list[Operation]
    meta: dict                    # filename, start/finish, signature, etc.
    visibility: Visibility        # "public", "private", or temporary "local"
    module: str | None            # MODULE name, or None for global
    type: dict | None = None      # Optional quotation TYPEDEF metadata


class TypeKey(bytes):
    """Opaque identifier for Joy TYPE_NAMEs used as struct type keys."""

    @classmethod
    def from_name(cls, name: str | bytes) -> "TypeKey":
        return cls(name if isinstance(name, bytes) else name.encode("utf-8"))

    def to_str(self) -> str:
        return self.decode("utf-8")


class JoyStruct:
    """Marker mixin for Joy struct instances. Provides .typename and .fields properties."""
    _joy_typename: TypeKey

    @property
    def typename(self) -> TypeKey:
        return type(self)._joy_typename

    @property
    def fields(self) -> tuple:
        """Backwards-compatible access to field values as tuple."""
        return tuple(self)


# All concrete Joy value types. Use in Search.inputs to require resolved values.
# Search placeholders are explicitly excluded — use Any if you need to match Search.
Value = int | float | Fraction | bool | str | bytes | list | dict | JoyStruct | Operation


class StructMeta(type):
    """Runtime type for Joy product structs; also carries TYPEDEF metadata.

    Each Joy `TYPEDEF` declaration is represented as a distinct Python class whose
    instances are namedtuples with named field access. The class object exposes
    `.name`, `.arity`, `.fields`, and `.instance_class` for use by combinators.
    """

    name: TypeKey
    arity: int
    fields: tuple[dict, ...]
    instance_class: type  # namedtuple subclass for this struct's values

    def __new__(mcls, name, bases, namespace, *, typename: TypeKey, fields: tuple[dict, ...]):
        cls = super().__new__(mcls, name, bases, namespace)
        cls.name = typename
        cls.arity = len(fields)
        cls.fields = tuple(fields)

        # Create namedtuple instance class with field labels
        labels = tuple(f.get("label") or f"field{i}" for i, f in enumerate(fields))
        nt_base = namedtuple(f"{name}", labels, rename=True)

        # Combine namedtuple with JoyStruct marker
        class InstanceClass(nt_base, JoyStruct):
            __slots__ = ()
            _joy_typename = typename
            _joy_field_defs = fields

        cls.instance_class = InstanceClass
        return cls

    @classmethod
    def from_typedef(mcls, typename: str, fields: tuple[dict, ...]) -> type:
        """Factory to create a StructMeta class from Joy TYPEDEF declaration."""
        type_key = TypeKey.from_name(typename)
        return mcls(typename, (object,), {}, typename=type_key, fields=fields)

    def __instancecheck__(cls, instance):
        # Check if instance was created via this struct's instance_class
        return isinstance(instance, cls.instance_class)


def validate_signature_inputs(expected: list[type], args: list[Any], name: str) -> tuple[bool, str]:
    """Validate that arguments match expected input types, as used by the interpreter (for Operations)
    and transformations (for Search).  The stack by convention, is left/bottom to right/top.
    
    Args:
        expected: Expected types in Joy bottom-first order (left-to-right).
        args:   Actual values in TOS-first order (args[0] = TOS).
        name:   Name for error messages.
    
    Returns:
        (True, "") if valid, (False, reason) if not.
    
    Note:
        Use `Value` in expected types to match any concrete Joy value (excludes Search).
        Use `Any` to match anything including Search placeholders.
    """
    if len(args) < len(expected):
        return False, f"`{name}` needs at least {len(expected)} item(s), but {len(args)} available."
    
    # Pair TOS-first args with reversed bottom-first expected types
    for i, (actual, expected_type) in enumerate(zip(args, reversed(expected))):
        if isinstance(expected_type, TypeVar):
            expected_type = expected_type.__bound__
        if expected_type in (Any, None):
            continue
        if not isinstance(actual, expected_type):
            type_name = getattr(expected_type, '__name__', str(expected_type))
            return False, f"`{name}` expects {type_name} at position {i+1} from top, got {type(actual).__name__}."
    
    return True, ""
