## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from joyfl.runtime import Runtime


def test_runtime_interpret_step_manual_queue():
    rt = Runtime()
    # Build a tiny program [2 3 add] and step it
    from collections import deque
    queue = deque([2, 3, rt.operation('add')])
    stack = rt.to_stack([])
    while queue:
        stack, queue = rt.do_step(queue, stack)
    assert rt.from_stack(stack) == [5]


def test_runtime_library_persistence_across_runs():
    rt = Runtime()
    lib = {}
    # define word in library module
    src_def = """
MODULE test

PUBLIC
    five == 5 ;
END.
"""
    lib = rt.load(src_def, filename='<LIB>', library=lib)
    stack = rt.run("five 3 + .", filename='<USE>', library=lib)
    assert rt.from_stack(stack) == [8]


def test_runtime_register_operation_without_annotations():
    rt = Runtime()
    def quadruple(x):
        return x * 4
    rt.register_operation('quadruple', quadruple)
    stack = rt.run("8 quadruple .")
    assert rt.from_stack(stack) == [32]


def test_runtime_register_operation_with_explicit_signature():
    rt = Runtime()
    def custom_op(a, b):
        return a + b, a * b
    
    rt.register_operation('custom-op', custom_op, signature={
        'arity': 2,
        'valency': 2,
        'inputs': [int, int],
        'outputs': [int, int]
    })
    
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


