## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from joyfl.types import Operation, TypeKey
from joyfl.errors import JoyUnknownStruct
from joyfl.linker import _populate_joy_definitions, load_joy_library
from joyfl.library import Library

import pytest


def _make_meta(line: int = 1) -> dict:
    return {"filename": "<test-recursion>", "lines": (line, line)}


def test_self_recursive_quotation_exec_ptr_is_resolved():
    """A quotation that calls itself should have its EXECUTE op patched to a program list."""
    lib = Library( functions={}, combinators={}, quotations={}, constants={}, factories={})

    # Define a word `loop` whose body is just a call to itself, enough to
    # exercise recursive resolution without needing the full Joy standard lib.
    meta_def = _make_meta()
    meta_tok = _make_meta()
    definitions = [
        ((None, "loop", meta_def), [(None, "loop", meta_tok)]),
    ]

    _populate_joy_definitions(definitions, lib=lib, visibility="public", module="test")

    quot = lib.quotations["loop"]
    assert isinstance(quot.program, list)

    # There should be a single EXECUTE operation calling `loop`, with its
    # pointer resolved to the quotation's program.
    [op] = [n for n in quot.program if isinstance(n, Operation)]
    assert op.type == Operation.EXECUTE
    assert op.name == "loop"
    assert op.ptr == quot.program


def test_mutually_recursive_quotations_exec_ptrs_are_resolved():
    """Two quotations that call each other should both have EXECUTE ptrs resolved."""
    lib = Library( functions={}, combinators={}, quotations={}, constants={}, factories={})

    meta_def = _make_meta()
    meta_tok_a = _make_meta()
    meta_tok_b = _make_meta()

    definitions = [
        ((None, "ping", meta_def), [(None, "pong", meta_tok_a)]),
        ((None, "pong", meta_def), [(None, "ping", meta_tok_b)]),
    ]

    _populate_joy_definitions(definitions, lib=lib, visibility="public", module="test")

    ping = lib.quotations["ping"]
    pong = lib.quotations["pong"]

    [op_ping] = [n for n in ping.program if isinstance(n, Operation)]
    [op_pong] = [n for n in pong.program if isinstance(n, Operation)]

    assert op_ping.type == Operation.EXECUTE
    assert op_ping.name == "pong"
    assert op_ping.ptr == pong.program

    assert op_pong.type == Operation.EXECUTE
    assert op_pong.name == "ping"
    assert op_pong.ptr == ping.program


def test_unknown_struct_type_in_signature_raises():
    """Stack-effect referring to undeclared struct TYPEDEF must raise JoyUnknownStruct."""
    export_lib = Library(functions={}, combinators={}, quotations={}, constants={}, factories={})
    context_lib = export_lib.with_overlay()

    sig = {"inputs": [TypeKey.from_name("MyPair")], "outputs": [], "arity": 1, "valency": 0}
    meta_def = {"filename": "<test>", "lines": (1, 1), "signature": sig}
    meta_tok = {"filename": "<test>", "lines": (1, 1)}

    sections = {"public": [((None, "use-pair", meta_def), [(None, "pop", meta_tok)])], "private": [], "types": [], "module": "m"}
    with pytest.raises(JoyUnknownStruct):
        load_joy_library(export_lib, sections, filename="<test>", context_lib=context_lib)
