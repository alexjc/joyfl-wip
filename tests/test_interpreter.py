## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from joyfl.api import Runtime
from joyfl.errors import JoyStackError

import pytest


def test_interpreter_output_validation_allows_matching_outputs():
    rt = Runtime()
    def good_op(a: int, b: int) -> tuple[int, int]: return a + b, a * b
    rt.register_operation("good-op", good_op)
    stack = rt.run("3 4 good-op .", validate=True)
    assert rt.from_stack(stack) == [12, 7]


def test_interpreter_output_validation_detects_mismatched_outputs():
    rt = Runtime()
    # Declares two outputs but only returns one value at runtime.
    def bad_op(a: int, b: int) -> tuple[int, int]: return (a + b,)
    rt.register_operation("bad-op", bad_op)
    with pytest.raises(JoyStackError):
        rt.run("3 4 bad-op .", validate=True)


def test_interpreter_output_validation_detects_too_many_outputs():
    rt = Runtime()
    # Declares two outputs but returns three values at runtime.
    def noisy_op(a: int, b: int) -> tuple[int, int]: return a, b, a + b
    rt.register_operation("noisy-op", noisy_op)
    with pytest.raises(JoyStackError):
        rt.run("3 4 noisy-op .", validate=True)
