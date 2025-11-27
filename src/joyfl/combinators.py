## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any

from .types import Operation, Stack, nil, JoyStruct, TypeKey, TYPE_NAME_MAP
from .errors import JoyError, JoyStackError, JoyNameError
from .parser import parse
from .formatting import show_stack, stack_to_list
from .interpreter import interpret


def comb_i(this: Operation, queue, stack: Stack, lib):
    """Takes a program as quotation on the top of the stack, and puts it into the queue for execution."""
    if stack is nil:
        raise JoyStackError("`i` needs a quotation on the stack.", joy_op=this)
    tail, head = stack
    if not isinstance(head, (list, tuple)):
        raise JoyStackError("`i` requires a quotation as list as top item on the stack.", joy_op=this)
    queue.extendleft(reversed(head))
    return tail

def comb_dip(this: Operation, queue, stack: Stack, lib):
    """Schedules a program for execution like `i`, but removes the second top-most item from the stack too
    and then restores it after the program is done.  This is like running `i` one level lower in the stack.
    """
    if stack is nil or stack.tail is nil:
        raise JoyStackError("`dip` needs at least 2 items on the stack.", joy_op=this)

    base, quotation = stack
    if not isinstance(quotation, (list, tuple)):
        raise JoyStackError("`dip` requires a quotation as list as top item on the stack.", joy_op=this)

    tail, item = base
    queue.appendleft(item)
    queue.extendleft(reversed(quotation))
    return tail

def comb_step(this: Operation, queue, stack: Stack, lib):
    """Applies a program to every item in a list in a recursive fashion.  `step` expands into another
    quotation that includes itself to run on the rest of the list, after the program was applied to the
    head of the list.
    """
    if stack is nil or stack.tail is nil:
        raise JoyStackError("`step` needs a list and quotation on the stack.", joy_op=this)

    (tail, values), program = stack

    if not isinstance(values, list):
        raise JoyStackError("`step` expects a list as second item on the stack.", joy_op=this)
    if not isinstance(program, (list, tuple)):
        raise JoyStackError("`step` expects a quotation as top item on the stack.", joy_op=this)
    if len(values) == 0: return tail

    queue.extendleft(reversed([values[0]] + program + [values[1:], program, this]))
    return tail

def comb_cont(this: Operation, queue, stack: Stack, lib):
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

def comb_exec_b(this: Operation, queue, stack: Stack, lib):
    """Evaluate a quotation on a fresh stack and capture outcome, returning either
    the entire stack or the error object, below a flag indicating success.

    : ([quot] -- result ok:bool)
    """
    if stack is nil:
        raise JoyStackError("`exec!` needs a quotation on the stack.", joy_op=this)

    tail, head = stack
    if not isinstance(head, (list, tuple)):
        raise JoyStackError("`exec!` requires a quotation as list as top item on the stack.", joy_op=this)

    is_ok, result = False, nil
    try:
        result_stack = interpret(head, stack=None, lib=lib, validate=True)
        is_ok, result = True, stack_to_list(result_stack)
    except JoyError as exc:
        result = exc

    return tail.pushed(result, is_ok)


def _get_expected_python_type_for_field(field: dict):
    """Resolve the Python type that a struct field is expected to hold."""
    if field.get("quote") is not None: return list
    type_name = (field.get("type") or "").lower()
    return TYPE_NAME_MAP.get(type_name, object)

def comb_struct(this: Operation, queue, stack: Stack, lib):
    """Construct a JoyStruct from N field values and a type symbol on the stack.

    Stack convention:
        - left field (first in typedef) = bottom of stack
        - right field (last in typedef) = top of stack

    e.g. MyPair :: a b  →  push a then b  →  'MyPair struct
    """

    if stack is nil:
        raise JoyStackError("`struct` expects 'TypeName literal as top of stack.", joy_op=this)

    base, type_symbol = stack
    if not isinstance(type_symbol, bytes):
        raise JoyStackError("`struct` expects 'TypeName literal as top of stack.", joy_op=this)

    type_key = TypeKey.from_name(type_symbol)
    if (meta := lib.struct_types.get(type_key)) is None:
        raise JoyNameError(f"Struct type {repr(type_key)[1:-1]} is not registered. Did you define it?", joy_op=this)

    # Pop all field values from stack right-to-left, must match in REVERSE order of definition.
    fields, current = [], base
    for idx, field_meta in enumerate(reversed(meta.fields), start=1):
        if current is nil:
            raise JoyStackError(f"`struct` for {repr(type_key)[1:-1]} needs at least {len(meta.fields)} field value(s) below the type symbol.", joy_op=this)
        current, value = current
        expected = _get_expected_python_type_for_field(field_meta)
        if expected not in (object, Any) and not isinstance(value, expected):
            label = field_meta.get("label") or f"field {len(meta.fields) - idx + 1}"
            raise JoyStackError(f"`struct` for {repr(type_key)[1:-1]} expects {expected.__name__} for {label}, got {type(value).__name__}.", joy_op=this)
        fields.append(value)

    # Reverse to get fields in declaration order (left-to-right)
    return Stack(current, meta.instance_class(*reversed(fields)))


def comb_unstruct(this: Operation, queue, stack: Stack, lib):
    """Explode a JoyStruct back into its fields on the stack."""

    if stack is nil:
        raise JoyStackError("`unstruct` expects a JoyStruct on top of the stack.", joy_op=this)

    base, top = stack
    if not isinstance(top, JoyStruct):
        raise JoyStackError(f"`unstruct` expects a JoyStruct, got {type(top).__name__}.", joy_op=this)

    type_key = top.typename
    if (meta := lib.struct_types.get(type_key)) is None:
        raise JoyNameError(f"Struct type {repr(type_key)[1:-1]} is not registered.", joy_op=this)

    if len(top) != meta.arity:
        raise JoyStackError(f"`unstruct` for {repr(type_key)[1:-1]} has {len(top)} field(s), expected {meta.arity}.", joy_op=this)

    result = base
    for value in top: # namedtuple is iterable directly
        result = Stack(result, value)
    return result
