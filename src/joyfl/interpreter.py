## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import sys
import collections

from typing import Any, TypeVar

from .types import Operation, Stack, nil
from .errors import JoyStackError
from .library import Library
from .formatting import show_program_and_stack, stack_to_list


def _operation_signature(op: Operation):
    if op.type == Operation.FUNCTION and hasattr(op.ptr, '__joy_meta__'):
        return op.ptr.__joy_meta__
    if isinstance(op.meta, dict) and 'signature' in op.meta:
        return op.meta['signature']
    return None


def can_execute(op: Operation, stack: Stack) -> tuple[bool, str]:
    """Check if operation can execute on stack using inferred stack effects."""
    # Special cases for combinators and runtime hazards that don't come from signature
    if op.type == Operation.COMBINATOR and op.name in ("i", "dip"):
        if stack is nil:
            return False, f"`{op.name}` needs at least 1 item on the stack, but stack is empty."
        _, head = stack
        if not isinstance(head, (list, tuple)):
            return False, f"`{op.name}` requires a quotation as list as top item on the stack."
        return True, ""

    # Division by zero guard for division, as binary int/float op.
    if op.name in ('div', '/') and stack is not nil:
        _, head = stack
        if head == 0:
            return False, f"`{op.name}` would divide by zero and cause a runtime exception."

    if (eff := _operation_signature(op)) is None: return True, ""

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


def interpret_step(program, stack, lib: Library):
    op = program.popleft()
    if isinstance(op, bytes) and op in (b'ABORT', b'BREAK'):
        print(f"\033[97m  ~ :\033[0m  ", end=''); show_program_and_stack(program, stack)
        if op == b'ABORT': sys.exit(-1)
        if op == b'BREAK': input()

    if not isinstance(op, Operation):
        stack = Stack(stack, op)
        return stack, program

    match op.type:
        case Operation.FUNCTION:
            stack = op.ptr(stack)
        case Operation.COMBINATOR:
            stack = op.ptr(op, program, *stack, lib=lib)
        case Operation.EXECUTE:
            program.extendleft(reversed(op.ptr))

    return stack, program


def interpret(program: list, stack=None, lib: Library = None, verbosity=0, validate=False, stats=None):
    stack = nil if stack is None else stack
    program = collections.deque(program)

    def is_notable(op):
        if not isinstance(op, Operation): return False
        return isinstance(op.ptr, list) or op.type == Operation.COMBINATOR

    step = 0
    while program:
        if validate and isinstance(program[0], Operation):
            if (check := can_execute(program[0], stack)) and not check[0]:
                raise JoyStackError(check[1], joy_op=program[0], joy_token=program[0].name, joy_stack=stack)

        if verbosity == 2 or (verbosity == 1 and (is_notable(program[0]) or step == 0)):
            print(f"\033[90m{step:>3} :\033[0m  ", end='')
            show_program_and_stack(program, stack)

        step += 1
        try:
            op = program[0]
            stack, program = interpret_step(program, stack, lib)
        except Exception as exc:
            exc.joy_op = op
            exc.joy_token = op.name
            exc.joy_stack = stack
            raise

    if verbosity > 0:
        print(f"\033[90m{step:>3} :\033[0m  ", end='')
        show_program_and_stack(program, stack)
    if stats is not None:
        stats['steps'] = stats.get('steps', 0) + step

    return stack
