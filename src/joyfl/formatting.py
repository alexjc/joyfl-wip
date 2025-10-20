## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import re
import sys

from .types import stack_list, Stack, nil


def stack_to_list(stk: Stack) -> stack_list:
    result = []
    while stk is not nil:
        stk, head = stk
        result.append(head)
    return stack_list(result)

def list_to_stack(values: list, base=None) -> Stack:
    stack = nil if base is None else base
    for value in reversed(values):
        stack = Stack(stack, value)
    return stack


def write_without_ansi(write_fn):
    """Wrapper function that strips ANSI codes before calling the original writer."""
    ansi_re = re.compile(r'\033\[[0-9;]*m')
    return lambda text: write_fn(ansi_re.sub('', text))

def format_item(it, width=None, indent=0):
    if (is_stack := isinstance(it, stack_list)) or isinstance(it, list):
        items = reversed(it) if is_stack else it
        lhs, rhs = ('<', '>') if is_stack else ('[', ']')
        formatted_items = [format_item(i, width, indent + 4) for i in items]
        single_line = lhs + ' '.join(formatted_items) + rhs
        # If it fits on one line, use single line format.
        if width is None or len(single_line) + indent <= width: return single_line
        # Otherwise use multi-line format...
        result = lhs + '   '
        for i, item in enumerate(formatted_items):
            if i > 0: result += '\n' + (' ' * (indent + 4))
            result += item
        result += '\n' + (' ' * indent) + rhs
        return result
    if isinstance(it, str) and indent > 0: return f'"{it.replace(chr(34), chr(92)+chr(34))}"'
    if isinstance(it, bool): return str(it).lower()
    if isinstance(it, bytes): return str(it)[1:-1]
    return str(it)

def show_stack(stack, width=72, end='\n', file=None):
    stack_str = ' '.join(format_item(s) for s in reversed(stack_to_list(stack))) if stack is not nil else '∅'
    if len(stack_str) > (width or sys.maxsize):
        stack_str = '… ' + stack_str[-width+2:]
    print(f"{stack_str:>{width}}" if width else stack_str, end=end, file=file)

def show_program_and_stack(program, stack, width=72):
    prog_str = ' '.join(format_item(p) for p in program) if program else '∅'
    if len(prog_str) > width:
        prog_str = prog_str[:+width-2] + ' …'
    show_stack(stack, end='')
    print(f" \033[36m <=> \033[0m {prog_str:<{width}}")
