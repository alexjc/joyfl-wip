## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import pytest

from joyfl import parser
from joyfl.errors import JoyParseError


def _parse_library(source: str):
    """Helper: parse a small library and return its public definitions."""
    items = list(parser.parse(source, filename="<test>"))
    # Expect a single library node: ('library', sections)
    [(_, sections)] = items
    return sections["public"]


def test_bracket_single_slot_is_single_stack_item():
    # `[bool]` and `[int]` should each be treated as a single list/quotation item
    src = """
    MODULE m
    PUBLIC
        f : ( [bool] -- [int] ) == ;
    END.
    """
    public_defs = _parse_library(src)
    # There should be exactly one public definition
    [(head, _body)] = public_defs
    sig = head[2]["signature"]

    assert sig["arity"] == 1
    assert sig["valency"] == 1
    # Both input and output should be represented as a list/quotation type
    assert sig["inputs"] == [list]
    assert sig["outputs"] == [list]


def test_bracket_multi_slot_is_single_stack_item():
    # `{pass:int fail:int}` should be a single list/quotation item on the stack
    src = """
    MODULE m
    PUBLIC
        g : ( [bool] -- {pass:int fail:int} ) == ;
    END.
    """
    public_defs = _parse_library(src)
    [(head, _body)] = public_defs
    sig = head[2]["signature"]

    assert sig["arity"] == 1
    assert sig["valency"] == 1
    # The structured list is still a single list/quotation at the meta level for now
    assert sig["inputs"] == [list]
    assert sig["outputs"] == [list]


def test_type_and_bracket_are_two_items_in_stack_pattern():
    # `list [bool]` is two separate inputs: a list and a list/quotation of bools.
    src = """
    MODULE m
    PUBLIC
        bad : ( list [bool] -- list ) == ;
    END.
    """
    public_defs = _parse_library(src)
    [(head, _body)] = public_defs
    sig = head[2]["signature"]

    # list [bool] -- list  →  two list-like inputs, one list-like output
    assert sig["arity"] == 2
    assert sig["valency"] == 1
    assert sig["inputs"] == [list, list]
    assert sig["outputs"] == [list]


def test_empty_brackets_in_stack_effect_are_rejected():
    src = """
    MODULE m
    PUBLIC
        bad : ( [] -- int ) == ;
    END.
    """
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))


def test_multi_param_brackets_in_stack_effect_are_rejected():
    src = """
    MODULE m
    PUBLIC
        bad : ( [a:int b:int] -- int ) == ;
    END.
    """
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))
