## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import joyfl.api as J


def test_run_string_add():
    stack = J.run("2 3 + .")
    assert J.from_stack(stack) == [5]


def test_program_building_and_run():
    stack = J.run("2 3 add .")
    assert J.from_stack(stack) == [5]


def test_register_operation_and_run():
    def inc(x: int) -> int: return x + 1
    J.register_operation('inc', inc)
    stack = J.run("4 inc .")
    assert J.from_stack(stack) == [5]


def test_register_operation_without_annotations():
    def double(x): return x * 2
    J.register_operation('double', double)
    stack = J.run("5 double .")
    assert J.from_stack(stack) == [10]


def test_register_factory_and_run():
    J.register_factory('x', lambda: {'x': 1})
    stack = J.run("@x .")
    top = J.from_stack(stack)[0]
    assert isinstance(top, dict) and top['x'] == 1


def test_introspection_helpers():
    sig = J.get_signature('add')
    assert sig['arity'] == 2
    ops = J.list_operations()
    assert 'add' in ops


def test_utilities_and_validation():
    s = J.to_stack([1, 2])
    assert J.from_stack(s) == [1, 2]
    ok, _ = J.can_step(J.operation('div'), J.to_stack([0, 1]))
    assert ok is False


def test_type_checks_and_predicates():
    assert J.is_operation(J.operation('add'))
    assert not J.is_quotation(J.operation('add'))
    assert J.is_quotation(J.quotation(1, 2))
    assert not J.is_operation(J.quotation(1, 2))
