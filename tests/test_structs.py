## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from joyfl.runtime import Runtime
from joyfl.types import StructInstance
from joyfl.errors import JoyNameError, JoyStackError

import pytest


def test_struct_type_registration_from_typedef():
    src = "MODULE m PUBLIC MyPair :: a b ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    key = b"MyPair"
    assert key in rt.library.struct_types
    meta = rt.library.struct_types[key]
    assert meta.name == key
    assert meta.arity == 2


def test_struct_roundtrip_runtime():
    src = "MODULE m PUBLIC MyPair :: a b ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    stack = rt.run("1 2 'MyPair struct .", filename="<TEST>")
    values = rt.from_stack(stack)
    assert len(values) == 1
    struct = values[0]
    assert isinstance(struct, StructInstance)
    assert struct.typename == b"MyPair"
    assert struct.fields == (1, 2)

    stack = rt.run("1 2 'MyPair struct destruct .", filename="<TEST>")
    # Stack order is from top to bottom; original stack after `1 2` was [2, 1],
    # so struct/destruct should behave as a no-op on the underlying stack.
    assert rt.from_stack(stack) == [2, 1]


def test_struct_type_with_stack_effect_field_registered_with_arity_and_metadata():
    src = "MODULE m PUBLIC MyCompositeType :: a b (d -- e) ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    key = b"MyCompositeType"
    assert key in rt.library.struct_types
    meta = rt.library.struct_types[key]

    # Two plain fields (a, b) plus one stack-effect field.
    assert meta.arity == 3
    assert len(meta.fields) == 3

    # First two entries are PARAM-derived.
    assert meta.fields[0]["label"] == "a"
    assert meta.fields[1]["label"] == "b"

    # Third entry represents a quotation field with attached stack-effect metadata.
    eff_field = meta.fields[2]
    assert eff_field["type"] == "list"
    assert isinstance(eff_field.get("quote"), dict)
    assert "inputs" in eff_field["quote"] and "outputs" in eff_field["quote"]


def test_struct_unknown_type_raises_name_error():
    rt = Runtime()
    # No TYPEDEF for MyUnknownType; struct should fail resolution.
    with pytest.raises(JoyNameError):
        rt.run("1 2 'MyUnknownType struct .", filename="<TEST>")


def test_struct_with_insufficient_fields_raises_stack_error():
    src = "MODULE m PUBLIC MyPair :: a b ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    # Only one value below the type symbol for a 2-field struct.
    with pytest.raises(JoyStackError):
        rt.run("1 'MyPair struct .", filename="<TEST>")


def test_struct_with_non_symbol_top_raises_stack_error():
    src = "MODULE m PUBLIC MyPair :: a b ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    # Top of stack is an int, not a `'MyPair` bytes symbol.
    with pytest.raises(JoyStackError):
        rt.run("1 2 3 struct .", filename="<TEST>")


def test_struct_with_incorrect_field_type_raises_stack_error():
    src = "MODULE m PUBLIC MyPair :: a:int b:int ; END."
    rt = Runtime()
    rt.load(src, filename="<TEST>")

    # First field is wrong type (str instead of int).
    with pytest.raises(JoyStackError):
        rt.run('"x" 2 \'MyPair struct .', filename="<TEST>")


