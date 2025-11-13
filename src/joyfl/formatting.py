## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import re
import sys

from .types import stack_list, Stack, nil


def stack_to_list(stk: Stack) -> stack_list:
    # Accept the current stack passed as a (tail, head) tuple (e.g., wrappers that call fn(*stk)).
    if isinstance(stk, tuple) and not isinstance(stk, Stack):
        tail, head = stk
        if tail is None and head is None:
            return stack_list([])
        # Fall through; the generic loop below will first unpack the pair,
        # then continue with the Stack in `tail`.
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

def _format_item(it, width=None, indent=0, abbreviate: bool = False):
    if (is_stack := isinstance(it, stack_list)) or isinstance(it, list):
        if abbreviate and not is_stack:
            return f'≪list:{len(it)}≫'
        items = reversed(it) if is_stack else it
        lhs, rhs = ('<', '>') if is_stack else ('[', ']')
        formatted_items = [_format_item(i, width, indent + 4, abbreviate=abbreviate) for i in items]
        single_line = lhs + ' '.join(formatted_items) + rhs
        # If it fits on one line, use single line format.
        if width is None or len(single_line) + indent <= width: return single_line
        # Otherwise use multi-line format...
        result = lhs + '   '
        for i, item in enumerate(reversed(formatted_items) if is_stack else formatted_items):
            if i > 0: result += '\n' + (' ' * (indent + 4))
            result += item
        result += '\n' + (' ' * indent) + rhs
        return result
    if isinstance(it, str):
        return f'≪string:{len(it)}≫' if abbreviate else '"' + it.replace('"', '\\"') + '"'
    if isinstance(it, bool): return str(it).lower()
    if isinstance(it, bytes): return str(it)[1:-1]
    return str(it)

def format_item(it, width=None, indent=0):
    return _format_item(it, width=width, indent=indent, abbreviate=False)

def show_stack(stack, width=72, end='\n', file=None, abbreviate: bool = False):
    if stack is nil:
        stack_str = '∅'
    else:
        items = stack_to_list(stack)
        # First render without abbreviation, check if it fits on screen.
        stack_str = ' '.join(_format_item(s, width=width, abbreviate=False) for s in reversed(items))
        # If abbreviation requested and the rendered output is long, re-render abbreviated.
        if abbreviate and len(stack_str) > 144:
            stack_str = ' '.join(_format_item(s, width=None, abbreviate=True) for s in reversed(items))

    if width is not None and len(stack_str) > width:
        stack_str = '… ' + stack_str[-width+2:]
    print(f"{stack_str:>{width}}" if width else stack_str, end=end, file=file)

def show_program_and_stack(program, stack, width=72):
    prog_str = ' '.join(format_item(p) for p in program) if program else '∅'
    if len(prog_str) > width:
        prog_str = prog_str[:+width-2] + ' …'
    show_stack(stack, end='')
    print(f" \033[36m <=> \033[0m {prog_str:<{width}}")
