## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from pathlib import Path
import os

from joyfl.errors import JoyNameError, JoyTypeMissing
from joyfl.runtime import Runtime
from joyfl.types import Stack
from joyfl.linker import link_body
from joyfl.parser import parse
from joyfl.loader import _LIB_MODULES

import pytest


def test_runtime_can_step_with_generic_alias_param():
    from dataclasses import dataclass

    @dataclass
    class Thing:
        value: int

    def use_list(xs: list[Thing]) -> Thing:
        return xs[0]

    rt = Runtime()
    # register operation with GenericAlias in signature
    rt.register_operation('use-list', use_list)

    # can_step should accept a list of Thing on the stack
    ok, msg = rt.can_step(rt.operation('use-list'), rt.to_stack([[Thing(1)]]))
    assert ok, msg

def test_runtime_can_step_with_pep604_union_param():
    rt = Runtime()

    def use_union(x: int | float) -> float:
        return float(x)

    rt.register_operation('use-union', use_union)

    ok, msg = rt.can_step(rt.operation('use-union'), rt.to_stack([2]))
    assert ok, msg

    ok, msg = rt.can_step(rt.operation('use-union'), rt.to_stack([2.0]))
    assert ok, msg

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


def _write_py_module(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / f"{name}.py"
    p.write_text(content, encoding="utf-8")
    return p


def _setup_py_module_env(monkeypatch, tmp_path: Path) -> None:
    # Search only our temp dir for Python-backed Joy modules.
    monkeypatch.setenv("JOY_PATH", str(tmp_path))
    # Ensure a fresh loader cache between tests.
    _LIB_MODULES.clear()


def test_runtime_python_module_multiple_operations(tmp_path, monkeypatch):
    module_source = (
        "def op_first(x: int) -> int:\n"
        "    return x + 1\n"
        "\n"
        "def op_second(x: int) -> int:\n"
        "    return x * 2\n"
        "\n"
        "__operators__ = [op_first, op_second]\n"
    )

    _write_py_module(tmp_path, "rtmod", module_source)
    _setup_py_module_env(monkeypatch, tmp_path)

    rt = Runtime()

    # First operation from the module should load and execute correctly.
    stack1 = rt.apply("rtmod.first", rt.to_stack([3]))
    assert rt.from_stack(stack1) == [4]

    # A second operation from the same module must also load correctly,
    # even though the namespace has already been accessed once.
    stack2 = rt.apply("rtmod.second", rt.to_stack([3]))
    assert rt.from_stack(stack2) == [6]

    # The underlying Python module itself should only be imported once.
    assert "rtmod" in _LIB_MODULES


def test_library_python_module_multiple_operations(tmp_path, monkeypatch):
    module_source = (
        "def op_first(x: int) -> int:\n"
        "    return x + 1\n"
        "\n"
        "def op_second(x: int) -> int:\n"
        "    return x * 2\n"
        "\n"
        "__operators__ = [op_first, op_second]\n"
    )

    _write_py_module(tmp_path, "rtmod2", module_source)
    _setup_py_module_env(monkeypatch, tmp_path)

    rt = Runtime()
    lib = rt.library

    fn_first = lib.get_function("rtmod2.first")
    fn_second = lib.get_function("rtmod2.second")

    assert callable(fn_first)
    assert callable(fn_second)
    assert fn_first is not fn_second


def _resolve_operation(rt: Runtime, name: str):
    term_tokens = None
    for typ, data in parse(f"{name}", start='term'):
        if typ == 'term':
            term_tokens = data
            break
    assert term_tokens is not None
    program, _ = link_body(term_tokens, meta={'filename': '<TEST>', 'lines': (1, 1)}, lib=rt.library)
    return program[0]


def test_runtime_can_step_rejects_insufficient_stack_for_joy_definition():
    rt = Runtime()
    rt.load("DEFINE foo : ( int bool -- ) == true .", filename='<TEST>', validate=False)
    op = _resolve_operation(rt, 'foo')

    ok, message = rt.can_step(op, rt.to_stack([True]))
    assert not ok
    assert "needs at least 2 item" in message


def test_runtime_can_step_validates_types_for_joy_definition():
    rt = Runtime()
    rt.load("DEFINE foo : ( int bool -- ) == true .", filename='<TEST>', validate=False)
    op = _resolve_operation(rt, 'foo')

    ok, _ = rt.can_step(op, rt.to_stack([True, 7]))
    assert ok

    ok, message = rt.can_step(op, rt.to_stack([1, 7]))
    assert not ok
    assert "expects bool" in message
