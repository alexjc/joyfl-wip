## Copyright © 2025, Alex J. Champandard.

from joyfl.api import Runtime


def run_and_items(src: str):
    rt = Runtime()
    out = rt.run(src)
    return rt.from_stack(out)


def test_exec_success():
    items = run_and_items("[ 1 2 + ] exec! .")
    # Top-first order: error, result-stack, ok?
    assert items[0] is True
    assert items[1] == [3]


def test_exec_failure():
    items = run_and_items("[ false assert! ] exec! .")
    assert items[0] is False
    assert items[1].__class__.__name__ == "JoyAssertionError"
