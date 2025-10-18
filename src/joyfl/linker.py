## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import ast
from typing import Callable
from fractions import Fraction

from . import operators
from .datatypes import Operation
from .errors import JoyNameError
from .loader import resolve_module_op, get_python_name
from .combinators import COMBINATORS
from .validating import get_stack_effects, _FUNCTION_SIGNATURES


CONSTANTS = {
    'true': True,
    'false': False,
}

FUNCTIONS = {
}

_FUNCTION_ALIASES = {
    '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'rem',
    '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte',
    '=': 'equal?', '!=': 'differ?', 'size': 'length',
}

def FUNC(x, meta={}):
    y, x = x, _FUNCTION_ALIASES.get(x, x)

    # Handle external libraries with dotted names.
    if '.' in x:
        if x not in FUNCTIONS:
            ns, local = x.split('.', 1)
            mod_fn = resolve_module_op(ns, local)
            FUNCTIONS[x] = _make_wrapper(mod_fn, x) if fn else None
    # Built-in operations defined above.
    elif x not in FUNCTIONS:
        op_fns = {k: getattr(operators, k) for k in dir(operators) if k.startswith('op_')}
        if (_name := get_python_name(x)) and _name not in op_fns:
            raise JoyNameError(f"Operation `{x}` not found in built-in library as `{_name}()`.", token=x)
        FUNCTIONS[x] = _make_wrapper(op_fns[_name], x)

    _FUNCTION_SIGNATURES.setdefault(y, _FUNCTION_SIGNATURES[x])
    if (fn := FUNCTIONS[x]) is None: return None
    return Operation(Operation.FUNCTION, fn, y, meta)

def COMB(x, meta={}):
    return Operation(Operation.COMBINATOR, COMBINATORS[x], x, meta)

def EXEC(x, prg, meta={}):
    return Operation(Operation.EXECUTE, prg, x, meta)


def _make_wrapper(fn: Callable, name: str) -> Callable:
    meta = get_stack_effects(fn=fn, name=name)
    arity = meta['arity']
    valency = meta['valency']

    # Build a small result pusher using valency
    if valency == -1:
        def push(_, res): return res
    elif valency == 0:
        def push(base, _): return base
    elif valency == 1:
        def push(base, res): return (base, res)
    else:
        def push(base, res):
            for v in res: base = (base, v)
            return base

    # Whole-stack reader, non-consuming
    if arity == -1:
        def w_n(stk: tuple):
            return push(stk, fn(*stk))
        return w_n
    elif arity == 1:
        def w_1(stk: tuple):
            base, a = stk
            return push(base, fn(a))
        return w_1
    elif arity == 2:
        def w_2(stk: tuple):
            (base, b), a = stk
            return push(base, fn(b, a))
        return w_2

    def w_x(stk: tuple):
        args, base = (), stk
        for _ in range(arity):
            base, h = base
            args = (h,) + args
        return push(base, fn(*args))
    return w_x


def link_body(tokens: list, library={}, meta={}):
    stack = tuple()
    output, meta = [], {'filename': meta['filename'], 'start': meta['lines'][0], 'finish': -1}

    for typ, token, mt in tokens:
        token = token.lstrip(':')

        if meta['filename'] == mt['filename'] and 'lines' in mt:
            meta['start'] = min(meta['start'], mt['lines'][0])
            meta['finish'] = max(meta['finish'], mt['lines'][1])
            mt['start'] = mt['lines'][0]; mt['finish'] = mt['lines'][1]; del mt['lines']

        if token == '[':
            stack = (stack, (output, meta))
            output, meta = [], mt
        elif token == ']':
            stack[-1][0].append(output)
            (stack, (output, meta)) = stack
        elif token in COMBINATORS:
            output.append(COMB(token, mt))
        elif token in CONSTANTS:
            output.append(CONSTANTS[token])
        elif token in library:
            if isinstance(library[token], tuple):
                prg, mt['body'] = library[token]
            else:
                prg = library[token]
            output.append(EXEC(token, prg, mt))
        elif token.startswith('"') and token.endswith('"'):
            output.append(ast.literal_eval(token))
        elif token.startswith("'"):
            output.append(bytes(token[1:], encoding='utf-8'))
        elif '⁄' in token[1:-1] and all(ch.isdigit() or ch == '⁄' for ch in token):
            output.append(Fraction(*map(int, token.split('⁄'))))
        elif token.isdigit() or token[0] == '-' and token[1:].isdigit():
            output.append(int(token))
        elif len(token) > 1 and token.count('.') == 1 and token.count('-') <= 1 and token.lstrip('-').replace('.', '').isdigit():
            output.append(float(token))
        elif (op := FUNC(token, mt)):
            output.append(op)
        else:
            raise JoyNameError(f"Unknown instruction `{token}`.", token=token)

    assert len(stack) == 0
    return output, meta
