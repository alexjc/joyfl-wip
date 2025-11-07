## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import pytest

from joyfl.errors import JoyTypeMissing
from joyfl.runtime import Runtime
from joyfl.types import Stack


def test_runtime_interpret_step_manual_queue():
    rt = Runtime()
    # Build a tiny program [2 3 add] and step it
    from collections import deque
    queue = deque([2, 3, rt.operation('add')])
    stack = rt.to_stack([])
    while queue:
        stack, queue = rt.do_step(queue, stack)
    assert rt.from_stack(stack) == [5]


def test_runtime_do_step_accepts_list():
    rt = Runtime()
    # Test that do_step accepts list and internally coerces to deque
    queue = [2, 3, rt.operation('add')]
    stack = rt.to_stack([])
    while queue:
        stack, queue = rt.do_step(queue, stack)
    assert rt.from_stack(stack) == [5]


def test_runtime_do_step_accepts_tuple():
    rt = Runtime()
    # Test that do_step accepts tuple and internally coerces to deque
    queue = (4, 5, rt.operation('mul'))
    stack = rt.to_stack([])
    while queue:
        stack, queue = rt.do_step(queue, stack)
    assert rt.from_stack(stack) == [20]


def test_runtime_apply():
    rt = Runtime()
    stack = rt.to_stack([3, 4])
    
    # Test with both Operation object and string name
    for op in [rt.operation('add'), 'add']:
        result = rt.apply(op, stack)
        assert rt.from_stack(result) == [7]
    
    # Test chaining
    stack = rt.to_stack([5])
    stack = rt.apply('dup', stack)
    stack = rt.apply(rt.operation('mul'), stack)
    assert rt.from_stack(stack) == [25]


def test_runtime_library_persistence_across_runs():
    rt = Runtime()

    src_def = """\
MODULE test

PUBLIC
    five == 5 ;
END.
"""
    rt.load(src_def, filename='<LIB>')
    stack = rt.run("five 3 + .", filename='<USE>')
    assert rt.from_stack(stack) == [8]


def test_runtime_register_operation_without_annotations():
    rt = Runtime()
    def quadruple(x): return x * 4
    with pytest.raises(JoyTypeMissing):
        rt.register_operation('quadruple', quadruple)


def test_runtime_variadic_stack_operation():
    rt = Runtime()

    def drop_top(*stack) -> Stack:
        rest, _ = stack
        return rest

    rt.register_operation('drop-top', drop_top)
    stack = rt.run("1 2 3 drop-top .")
    assert rt.from_stack(stack) == [2, 1]


def test_runtime_register_operation_with_explicit_signature():
    rt = Runtime()
    def custom_op(a: int, b: int) -> tuple[int, int]: 
        return a + b, a * b

    rt.register_operation('custom-op', custom_op)

    stack = rt.run("3 4 custom-op .")
    assert rt.from_stack(stack) == [12, 7]
    
    sig = rt.get_signature('custom-op')
    assert sig['arity'] == 2
    assert sig['valency'] == 2


def test_runtime_register_factory():
    rt = Runtime()
    
    class TestObject:
        def __init__(self):
            self.value = 42
    
    rt.register_factory('testobj', TestObject)
    stack = rt.run("@testobj .")
    result = rt.from_stack(stack)[0]
    assert isinstance(result, TestObject)
    assert result.value == 42


def test_runtime_preserves_quotations_and_order():
    rt = Runtime()
    cases = [
        ("[1 2 3]", [[1, 2, 3]]),
        ("[1 [2 3] 4]", [[1, [2, 3], 4]]),
        ("[1 2] [3 [4]]", [[3, [4]], [1, 2]]),
    ]
    for code, expected in cases:
        stack = rt.run(code + " .")
        assert rt.from_stack(stack) == expected
