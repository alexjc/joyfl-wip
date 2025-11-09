## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any

import pytest

from joyfl.errors import JoyTypeMissing, JoyTypeError
from joyfl.loader import get_stack_effects
from joyfl.types import Stack


def test_stack_effects_supports_generic_alias_list_of_dataclass() -> None:
    from dataclasses import dataclass

    @dataclass
    class Thing:
        value: int

    def op_generic(xs: list[Thing]) -> Thing:
        return xs[0]

    meta = get_stack_effects(fn=op_generic, name='generic')
    assert meta['arity'] == 1
    assert meta['valency'] == 1
    # inputs should be isinstance-safe; list[Thing] should normalize to list
    assert meta['inputs'] == [list]
    assert meta['outputs'] == [Thing]


def test_stack_effects_supports_pep604_union_param() -> None:
    def op_union(x: int | float) -> int:
        return int(x)

    meta = get_stack_effects(fn=op_union, name='union')
    assert meta['arity'] == 1
    assert meta['valency'] == 1
    # Keep PEP 604 union unchanged for isinstance checks
    assert meta['inputs'] == [int | float]
    assert meta['outputs'] == [int]

def test_stack_effects_requires_positional_only_param_annotations() -> None:
    def op_missing_pos_only(a, /, b: int) -> int:
        return a + b

    # `a` is a positional-only parameter without annotation; should be rejected early.
    with pytest.raises(JoyTypeMissing, match=r"annotate parameters: a"):
        get_stack_effects(fn=op_missing_pos_only, name='missing_pos_only')


def test_stack_effects_raises_on_unsupported_string_annotation() -> None:
    def op_str_annot(a: 'int') -> int:
        return int(a)

    with pytest.raises(JoyTypeError, match=r"not supported"):
        get_stack_effects(fn=op_str_annot, name='str_annot')

def test_stack_effects_requires_return_annotation() -> None:
    def op_missing(a: int):
        return a

    with pytest.raises(JoyTypeMissing, match=r"return annotation"):
        get_stack_effects(fn=op_missing, name='missing')


def test_stack_effects_requires_parameter_annotations() -> None:
    def op_missing_param(a, b: int) -> int:
        return a + b

    with pytest.raises(JoyTypeMissing, match=r"annotate parameters: a"):
        get_stack_effects(fn=op_missing_param, name='missing_param')


def test_vararg_requires_annotation_unless_stack_form() -> None:
    def op_bad(*items) -> int:
        return len(items)

    with pytest.raises(JoyTypeMissing, match=r"variadic stack form"):
        get_stack_effects(fn=op_bad, name='bad_vararg')


def test_vararg_with_annotation_is_allowed() -> None:
    def op_good(*items: Any) -> int:
        return len(items)

    meta = get_stack_effects(fn=op_good, name='good_vararg')
    assert meta['arity'] == -1
    assert meta['valency'] == 1


def test_variadic_stack_form_allowed() -> None:
    def op_reset(*stack) -> Stack:
        raise NotImplementedError

    meta = get_stack_effects(fn=op_reset, name='reset')
    assert meta['arity'] == -1
    assert meta['valency'] == -1

