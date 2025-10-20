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


