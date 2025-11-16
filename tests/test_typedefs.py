## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from joyfl import parser
from joyfl.errors import JoyParseError

import pytest


def _parse_ok(source: str) -> None:
    list(parser.parse(source, filename="<test>"))


def test_product_type_definitions_basic():
    # Simple product type with plain fields.
    src = "MODULE m PUBLIC MyStructType :: a b ; END."
    _parse_ok(src)


def test_product_type_definitions_with_type_hints_and_stack_effect():
    # Product type with type-hinted fields and stack-effect field.
    src = """
    MODULE m
    PUBLIC
        MyStructTypeWithTypes :: a:int b:float c:bool ;
        MyCompositeType :: a b (d -- e) ;
        MyOperationType :: (d -- e) ;
        MyComplexOperationType :: (MyTupleType -- e) ;
    END.
    """
    _parse_ok(src)


def test_sum_type_definitions_with_constructors():
    # Sum types with multiple constructors and mixed field forms.
    src = """
    MODULE m
    PUBLIC
        Maybe :: Just a | Nothing ;
        Result :: Ok value | Error code message ;
        Shape :: Circle radius:float | Rectangle width:float height:float ;
        Action :: Move dx:int dy:int | Wait ;
    END.
    """
    _parse_ok(src)


def test_type_definitions_only_allowed_in_library_sections():
    # Type definitions should not be accepted as free-standing terms.
    bad_src = "Maybe :: Just a | Nothing ."
    with pytest.raises(JoyParseError):
        list(parser.parse(bad_src, filename="<test>"))


@pytest.mark.parametrize(
    "typename",
    [
        "maybe",   # starts with lowercase
        "Maybe1",  # contains digit
        "Maybe_",  # contains punctuation
        "MAYBE",   # does not end with lowercase
    ],
)
def test_invalid_type_name_forms_are_rejected(typename: str):
    src = f"MODULE m PUBLIC {typename} :: a b ; END."
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))


@pytest.mark.parametrize(
    "src",
    [
        # Missing constructor or field list after TYPEDEF.
        "MODULE m PUBLIC Maybe :: ; END.",
        # Trailing BAR without constructor.
        "MODULE m PUBLIC Maybe :: Just a | ; END.",
    ],
)
def test_malformed_type_definitions_are_rejected(src: str):
    with pytest.raises(JoyParseError):
        list(parser.parse(src, filename="<test>"))
