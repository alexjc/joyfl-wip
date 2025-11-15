## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
from pathlib import Path

import pytest

from joyfl.errors import JoyNameError
from joyfl.runtime import Runtime


def test_library_persistence_across_runs():
    rt = Runtime()

    src_def = "MODULE test PUBLIC five == 5 ; END."
    rt.load(src_def, filename="<LIB>")
    stack = rt.run("test.five 3 + .", filename="<USE>")
    assert rt.from_stack(stack) == [8]


def test_library_private_definitions_available_to_public():
    rt = Runtime()

    src_def = "MODULE test PRIVATE helper == 41 ; PUBLIC answer == helper 1 + ; END."
    rt.load(src_def, filename="<LIB>")
    stack = rt.run("test.answer .", filename="<USE>")
    assert rt.from_stack(stack) == [42]


def test_library_private_definitions_not_exported():
    rt = Runtime()

    src_def = "MODULE test PRIVATE helper == 41 ; PUBLIC answer == helper 1 + ; END."
    rt.load(src_def, filename="<LIB>")

    # Private helper should not be callable from outside the module.
    with pytest.raises(JoyNameError):
        rt.run("helper .", filename="<USE>")


def test_library_private_name_clashes_between_modules_are_isolated():
    rt = Runtime()

    src_mod1 = "MODULE one PRIVATE helper == 1   ; PUBLIC answer1 == helper 1 + ; END."
    src_mod2 = "MODULE two PRIVATE helper == 100 ; PUBLIC answer2 == helper 2 + ; END."

    rt.load(src_mod1, filename="<LIB1>")
    rt.load(src_mod2, filename="<LIB2>")

    # Each public word should continue to use the helper it was linked with.
    stack1 = rt.run("one.answer1 .", filename="<USE1>")
    stack2 = rt.run("two.answer2 .", filename="<USE2>")

    assert rt.from_stack(stack1) == [2]
    assert rt.from_stack(stack2) == [102]


def test_library_private_helper_does_not_override_public_helper_from_other_module():
    rt = Runtime()

    src_mod_public = "MODULE one PUBLIC helper == 10 ; use-public-helper == helper 1 + ; END."
    src_mod_private = "MODULE two PRIVATE helper == 100 ; PUBLIC use-private-helper == helper 2 + ; END."

    rt.load(src_mod_public, filename="<LIB1>")
    rt.load(src_mod_private, filename="<LIB2>")

    # The public helper from module `one` should remain callable and unchanged.
    stack_public = rt.run("one.helper .", filename="<USE-public>")
    assert rt.from_stack(stack_public) == [10]

    # The public word in module `two` must still use its own PRIVATE helper.
    stack_private = rt.run("two.use-private-helper .", filename="<USE-private>")
    assert rt.from_stack(stack_private) == [102]


