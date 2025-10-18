## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import sys
import traceback
import collections

from typing import Any, TypeVar

from .types import Operation
from .parser import print_source_lines
from .formatting import show_stack, show_program_and_stack, stack_to_list
from .loader import get_stack_effects


def can_execute(op: Operation, stack: tuple, library={}) -> tuple[bool, str]:
    """Check if operation can execute on stack using inferred stack effects."""
    # Special cases for combinators and runtime hazards that don't come from signature
    if op.type == Operation.COMBINATOR and op.name in ("i", "dip"):
        if not stack or stack == tuple():
            return False, f"`{op.name}` needs at least 1 item on the stack, but stack is empty."
        _, head = stack
        if not isinstance(head, (list, tuple)):
            return False, f"`{op.name}` requires a quotation as list as top item on the stack."
        return True, ""

    # Division by zero guard for division, as binary int/float op.
    if op.name in ('div', '/') and stack and stack != tuple():
        _, head = stack
        if head == 0:
            return False, f"`{op.name}` would divide by zero and cause a runtime exception."

    if op.type != Operation.FUNCTION: return True, ""

    eff = get_stack_effects(name=op.name)
    inputs = eff['inputs']
    items = stack_to_list(stack)
    depth = len(items)
    if depth < len(inputs):
        need = len(inputs)
        return False, f"`{op.name}` needs at least {need} item(s) on the stack, but {depth} available."

    # Type checks from top downward
    for i, expected_type in enumerate(inputs):
        if isinstance(expected_type, TypeVar): expected_type = expected_type.__bound__
        if expected_type in (Any, None): continue
        actual = items[i]
        if not isinstance(actual, expected_type):
            type_name = expected_type.__name__ if hasattr(expected_type, '__name__') else str(expected_type)
            return False, f"`{op.name}` expects {type_name} at position {i+1} from top, got {type(actual).__name__}."

    # Extra semantic guard for 'index' bounds when types look correct
    if op.name == 'index' and len(items) >= 2 and isinstance(items[0], (list, str)) and isinstance(items[1], int):
        idx, seq = items[1], items[0]
        if not (0 <= int(idx) < len(seq)):
            return False, f"`{op.name}` would index a list out ouf bounds."

    return True, ""


def interpret_step(program, stack, library={}):
    op = program.popleft()
    if isinstance(op, bytes) and op in (b'ABORT', b'BREAK'):
        print(f"\033[97m  ~ :\033[0m  ", end=''); show_program_and_stack(program, stack)
        if op == b'ABORT': sys.exit(-1)
        if op == b'BREAK': input()

    if not isinstance(op, Operation):
        stack = (stack, op)
        return stack, program

    match op.type:
        case Operation.FUNCTION:
            stack = op.ptr(stack)
        case Operation.COMBINATOR:
            stack = op.ptr(op, program, *stack, library=library)
        case Operation.EXECUTE:
            program.extendleft(reversed(op.ptr))

    return stack, program


def interpret(program: list, stack=None, library={}, verbosity=0, validate=False, stats=None):
    stack = tuple() if stack is None else stack
    program = collections.deque(program)

    def is_notable(op):
        if not isinstance(op, Operation): return False
        return isinstance(op.ptr, list) or op.type == Operation.COMBINATOR

    step = 0
    while program:
        if validate and isinstance(program[0], Operation):
            if (check := can_execute(program[0], stack, library)) and not check[0]:
                print(f'\033[30;43m TYPE ERROR. \033[0m {check[1]}\n', file=sys.stderr)
                print(f'\033[1;33m  Stack content is\033[0;33m\n    ', end='', file=sys.stderr)
                show_stack(stack, width=None, file=sys.stderr)
                print('\033[0m', file=sys.stderr)
                print_source_lines(program[0], library, file=sys.stderr)
                break
        
        if verbosity == 2 or (verbosity == 1 and (is_notable(program[0]) or step == 0)):
            print(f"\033[90m{step:>3} :\033[0m  ", end='')
            show_program_and_stack(program, stack)

        step += 1
        try:
            op = program[0]
            stack, program = interpret_step(program, stack, library)
        except AssertionError as exc:
            print(f'\033[30;43m ASSERTION FAILED. \033[0m Function \033[1;97m`{op}`\033[0m raised an error.\n', file=sys.stderr)
            print_source_lines(op, library, file=sys.stderr)
            print(f'\033[1;33m  Stack content is\033[0;33m\n    ', end='', file=sys.stderr)
            show_stack(stack, width=None, file=sys.stderr); print('\033[0m', file=sys.stderr)
            return
        except Exception as exc:
            print(f'\033[30;43m RUNTIME ERROR. \033[0m Function \033[1;97m`{op}`\033[0m caused an error in interpret! (Exception: \033[33m{type(exc).__name__}\033[0m)\n', file=sys.stderr)
            tb_lines = traceback.format_exc().split('\n')
            print(*[line for line in tb_lines if 'lambda' in line], sep='\n', end='\n', file=sys.stderr)
            print_source_lines(op, library, file=sys.stderr)
            traceback.print_exc()
            return

    if verbosity > 0:
        print(f"\033[90m{step:>3} :\033[0m  ", end='')
        show_program_and_stack(program, stack)
    if stats is not None:
        stats['steps'] = stats.get('steps', 0) + step

    return stack
