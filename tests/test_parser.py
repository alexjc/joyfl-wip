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


def _parse_types(source: str):
    """Helper: parse a small library and return its type definitions metadata."""
    items = list(parser.parse(source, filename="<test>"))
    [(_, sections)] = items
    return sections["types"]


def test_bracket_single_slot_is_single_stack_item():
    # `[bool]` and `[int]` should each be treated as a single list/quotation item
    src = """MODULE m PUBLIC f : ( [bool] -- [int] ) == ; END."""
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
    src = """MODULE m PUBLIC g : ( [bool] -- {pass:int fail:int} ) == ; END.
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
    src = """MODULE m PUBLIC bad : ( list [bool] -- list ) == ; END."""
    public_defs = _parse_library(src)
    [(head, _body)] = public_defs
    sig = head[2]["signature"]

    # list [bool] -- list  →  two list-like inputs, one list-like output
    assert sig["arity"] == 2
    assert sig["valency"] == 1
    assert sig["inputs"] == [list, list]
    assert sig["outputs"] == [list]


def test_empty_brackets_in_stack_effect_are_rejected():
    src = """MODULE m PUBLIC bad : ( [] -- int ) == ; END."""
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))


def test_multi_param_brackets_in_stack_effect_are_rejected():
    src = """MODULE m PUBLIC bad : ( [a:int b:int] -- int ) == ; END."""
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))


def test_typedef_list_wrapped_primitives():
    # Typedef fields using list-wrapped primitives should preserve inner type metadata.
    src = """MODULE m
    PUBLIC
        Numbers :: [xs:int] ;
        Names   :: [names:str] ;
        Flags   :: [flags:bool] ;
    END.
    """
    types = _parse_types(src)

    # Expect three public product types
    assert len(types) == 3

    vis1, name1, meta1 = types[0]
    assert vis1 == "public"
    assert name1 == "Numbers"
    assert meta1["kind"] == "product"
    [field1] = meta1["fields"]
    assert field1["label"] == "xs"
    assert field1["type"] == "list"
    [inner1] = field1["quote"]
    assert inner1["label"] == "xs"
    assert inner1["type"] == "int"

    vis2, name2, meta2 = types[1]
    assert vis2 == "public"
    assert name2 == "Names"
    assert meta2["kind"] == "product"
    [field2] = meta2["fields"]
    assert field2["label"] == "names"
    assert field2["type"] == "list"
    [inner2] = field2["quote"]
    assert inner2["label"] == "names"
    assert inner2["type"] == "str"

    vis3, name3, meta3 = types[2]
    assert vis3 == "public"
    assert name3 == "Flags"
    assert meta3["kind"] == "product"
    [field3] = meta3["fields"]
    assert field3["label"] == "flags"
    assert field3["type"] == "list"
    [inner3] = field3["quote"]
    assert inner3["label"] == "flags"
    assert inner3["type"] == "bool"


def test_typedef_list_wrapped_custom_type():
    # Typedef field `[tests:TestCase]` should become a list-valued field with inner custom type.
    src = """MODULE m
    PUBLIC
        TestCase  :: desc:str code:list ;
        FileTests :: filename:str [tests:TestCase] ;
    END.
    """
    types = _parse_types(src)

    assert len(types) == 2

    vis_tc, name_tc, meta_tc = types[0]
    assert vis_tc == "public"
    assert name_tc == "TestCase"
    assert meta_tc["kind"] == "product"
    assert [f["label"] for f in meta_tc["fields"]] == ["desc", "code"]

    vis_ft, name_ft, meta_ft = types[1]
    assert vis_ft == "public"
    assert name_ft == "FileTests"
    assert meta_ft["kind"] == "product"

    # First field: filename:str
    field_filename, field_tests = meta_ft["fields"]
    assert field_filename["label"] == "filename"
    assert field_filename["type"].lower() == "str"

    # Second field: [tests:TestCase] as a list-valued field preserving inner label/type.
    assert field_tests["label"] == "tests"
    assert field_tests["type"] == "list"
    [inner_tests] = field_tests["quote"]
    assert inner_tests["label"] == "tests"
    assert inner_tests["type"] == "TestCase"
