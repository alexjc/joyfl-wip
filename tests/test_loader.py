from typing import Any

import pytest

from joyfl.errors import JoyTypeMissing
from joyfl.loader import get_stack_effects
from joyfl.types import Stack


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

