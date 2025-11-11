## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from .types import Operation
from .parser import parse
from .formatting import show_stack


def comb_i(_, queue, tail, head, lib):
    """Takes a program as quotation on the top of the stack, and puts it into the queue for execution."""
    assert isinstance(head, (list, tuple))
    queue.extendleft(reversed(head))
    return tail

def comb_dip(_, queue, *stack, lib):
    """Schedules a program for execution like `i`, but removes the second top-most item from the stack too
    and then restores it after the program is done.  This is like running `i` one level lower in the stack.
    """
    ((tail, item), head) = stack
    assert isinstance(head, list)
    queue.appendleft(item)
    queue.extendleft(reversed(head))

    return tail

def comb_step(this: Operation, queue, *stack, lib):
    """Applies a program to every item in a list in a recursive fashion.  `step` expands into another
    quotation that includes itself to run on the rest of the list, after the program was applied to the
    head of the list.
    """
    (tail, values), program = stack
    assert isinstance(program, list) and isinstance(values, list)
    if len(values) == 0: return tail
    queue.extendleft(reversed([values[0]] + program + [values[1:], program, this]))
    return tail

def comb_cont(this: Operation, queue, *stack, lib):
    from .linker import link_body

    print(f"\033[97m  ~ :\033[0m  ", end=''); show_stack(stack, width=72, end='')
    try:
        program = []
        value = input("\033[4 q\033[36m  ...  \033[0m")
        if value.strip():
            for typ, data in parse(value, start='term'):
                program, _ = link_body(data, meta={'filename': '<REPL>', 'lines': (1, 1)}, lib=lib)
    except Exception as e:
        print('EXCEPTION: comb_cont could not parse or compile the text.', e)
        import traceback; traceback.print_exc(limit=2)
    finally:
        print("\033[0 q", end='')

    if program:
        queue.extendleft(reversed(program + [this]))
    return stack
