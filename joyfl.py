## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import os
import re
import ast
import sys
import math
import time
import inspect
import textwrap
import readline
import traceback
import collections

from fractions import Fraction
from types import UnionType
from typing import Any, Callable, get_origin, get_args, TypeVar
import click


class stack_list(list): pass


def stack_to_list(stk: tuple) -> stack_list:
    result = []
    while stk:
        stk, head = stk
        result.append(head)
    return stack_list(result)

def list_to_stack(values: list, base=None) -> tuple:
    stack = tuple() if base is None else base
    for value in reversed(values):
        stack = (stack, value)
    return stack


def _write_without_ansi(write_fn):
    """Wrapper function that strips ANSI codes before calling the original writer."""
    ansi_re = re.compile(r'\033\[[0-9;]*m')
    return lambda text: write_fn(ansi_re.sub('', text))

def _format_item(it, width=None, indent=0):
    if (is_stack := isinstance(it, stack_list)) or isinstance(it, list):
        items = reversed(it) if is_stack else it
        lhs, rhs = ('<', '>') if is_stack else ('[', ']')
        formatted_items = [_format_item(i, width, indent + 4) for i in items]
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
    stack_str = ' '.join(_format_item(s) for s in reversed(stack_to_list(stack))) if stack else '∅'
    if len(stack_str) > (width or sys.maxsize):
        stack_str = '… ' + stack_str[-width+2:]
    print(f"{stack_str:>{width}}" if width else stack_str, end=end, file=file)

def show_program_and_stack(program, stack, width=72):
    prog_str = ' '.join(_format_item(p) for p in program) if program else '∅'
    if len(prog_str) > width:
        prog_str = prog_str[:+width-2] + ' …'
    show_stack(stack, end='')
    print(f" \033[36m <=> \033[0m {prog_str:<{width}}")


class Operation:
    FUNCTION = 1
    COMBINATOR = 2
    EXECUTE = 3

    def __init__(self, type, ptr, name, meta={}):
        self.type = type
        self.ptr = ptr
        self.name = name
        self.meta = meta

    def __eq__(self, other):
        return isinstance(other, Operation) and self.type == other.type and self.ptr == other.ptr

    def __repr__(self):
        return f"{self.name}"


def comb_i(_, queue, tail, head, library={}):
    """Takes a program as quotation on the top of the stack, and puts it into the queue for execution."""
    assert isinstance(head, (list, tuple))
    queue.extendleft(reversed(head))
    return tail

def comb_dip(_, queue, *stack, library={}):
    """Schedules a program for execution like `i`, but removes the second top-most item from the stack too
    and then restores it after the program is done.  This is like running `i` one level lower in the stack.
    """
    ((tail, item), head) = stack
    assert isinstance(head, list)
    queue.appendleft(item)
    queue.extendleft(reversed(head))

    return tail

def comb_step(this: Operation, queue, *stack, library={}):
    """Applies a program to every item in a list in a recursive fashion.  `step` expands into another
    quotation that includes itself to run on the rest of the list, after the program was applied to the
    head of the list.
    """
    (tail, values), program = stack
    assert isinstance(program, list) and isinstance(values, list)
    if len(values) == 0: return tail
    queue.extendleft(reversed([values[0]] + program + [values[1:], program, this]))
    return tail

def comb_cont(this: Operation, queue, *stack, library={}):
    print(f"\033[97m  ~ :\033[0m  ", end=''); show_stack(stack, width=72, end='')
    try:
        program = []
        value = input("\033[4 q\033[36m  ...  \033[0m")
        if value.strip():
            for typ, data in parse(value, start='term'):
                program, _ = compile_body(data, library, meta={'filename': '<REPL>', 'lines': (1, 1)})
    except Exception as e:
        print('EXCEPTION: comb_cont could not parse or compile the text.', e)
        traceback.print_exc(limit=2)
    finally:
        print("\033[0 q", end='')

    if program:
        queue.extendleft(reversed(program + [this]))
    return stack


# lambda QUEUE, STACK: NEW_STACK
COMBINATORS = {
    'i': comb_i,
    'dip': comb_dip,
    'step': comb_step,
    ',,,': comb_cont,
}

FUNCTIONS = {}
num = int | float

## ARITHMETIC
def op_add(b: num, a: num) -> num: return b + a
def op_sub(b: num, a: num) -> num: return b - a
def op_neg(x: num) -> num: return -x
def op_abs(x: num) -> num: return abs(x)
def op_sign(x: num) -> num: return (x > 0) - (x < 0)
def op_min(b: num, a: num) -> num: return min(b, a)
def op_max(b: num, a: num) -> num: return max(b, a)
def op_mul(b: num, a: num) -> num: return b * a
def op_div(b: num, a: num) -> num: return b / a
def op_rem(b: num, a: num) -> num: return b % a
def op_equal_q(b: Any, a: Any) -> bool: return b == a
def op_differ_q(b: Any, a: Any) -> bool: return b != a
## BOOLEAN LOGIC
def op_gt(b: num, a: num) -> bool: return b > a
def op_gte(b: num, a: num) -> bool: return b >= a
def op_lt(b: num, a: num) -> bool: return b < a
def op_lte(b: num, a: num) -> bool: return b <= a
def op_and(b: bool, a: bool) -> bool: return b and a
def op_or(b: bool, a: bool) -> bool: return b or a
def op_not(x: bool) -> bool: return not x
def op_xor(b: Any, a: Any) -> Any: return b ^ a
## DATA & INTROSPECTION
def op_null_q(x: Any) -> bool: return (len(x) if isinstance(x, (list, str)) else x) == 0
def op_small_q(x: Any) -> bool: return (len(x) if isinstance(x, (list, str)) else x) < 2
def op_sametype_q(b: Any, a: Any) -> bool: return type(b) == type(a)
def op_integer_q(x: Any) -> bool: return isinstance(x, int)
def op_float_q(x: Any) -> bool: return isinstance(x, float)
def op_list_q(x: Any) -> bool: return isinstance(x, list)
def op_string_q(x: Any) -> bool: return isinstance(x, str)
def op_boolean_q(x: Any) -> bool: return isinstance(x, bool)
## LIST MANIPULATION
def op_cons(b: Any, a: list) -> list: return [b] + a
def op_append(b: Any, a: list) -> list: return a + [b]
def op_remove(b: list, a: Any) -> list: return [x for x in b if x != a]
def op_take(b: list, a: int) -> list: return b[:a]
def op_drop(b: list, a: int) -> list: return b[a:]
def op_uncons(x: list) -> tuple[Any, list]: return (x[0], x[1:])
def op_concat(b: list, a: list) -> list: return b + a
def op_reverse(x: list) -> list: return list(reversed(x))
def op_first(x: list) -> Any: return x[0]
def op_rest(x: list) -> list: return x[1:]
def op_last(x: list) -> Any: return x[-1]
def op_index(b: int, a: list) -> Any: return a[int(b)]
def op_member_q(b: Any, a: list) -> bool: return b in a
def op_length(x: Any) -> int: return len(x)
def op_sum(x: list) -> num: return sum(x)
def op_product(x: list) -> num: return math.prod(x)
# STACK OPERATIONS
X, Y = (TypeVar(v, bound=Any) for v in ('X', 'Y'))
def op_swap(b: Y, a: X) -> tuple[X, Y]: return (a, b)
def op_dup(x: X) -> tuple[X, X]: return (x, x)
def op_pop(_: Any) -> None: return None
def op_stack(*s: Any) -> list: return stack_to_list(s)
def op_unstack(x: list) -> tuple: return list_to_stack(x)
def op_stack_size(*s: Any) -> int: return len(stack_to_list(s))
# INPUT/OUTPUT
def op_id(x: Any) -> Any: return x
def op_put_b(x: Any) -> None: print('\033[97m' + _format_item(x, width=120) + '\033[0m')
def op_assert_b(x: bool) -> None: assert x
def op_raise_b(x: Any) -> None: raise x
# STRING MANIPULATION
def op_str_concat(b: str, a: str) -> str: return str(b) + str(a)
def op_str_contains_q(b: str, a: str) -> bool: return str(b) in str(a)
def op_str_split(b: str, a: str) -> Any: return a.split(b)
# DICTIONARIES (mutable)
def op_dict_new() -> dict: return {}
def op_dict_store(d: dict, k: bytes, v: Any) -> dict: return d.__setitem__(k, v) or d
def op_dict_fetch(d: dict, k: bytes) -> Any: return d[k]



CONSTANTS = {
    'true': True,
    'false': False,
}


GRAMMAR = r"""?start: (library | term DOT)*
library: module_clause? private_clause? public_clause? (END | DOT)+
module_clause: "MODULE" NAME
private_clause: ("PRIVATE" | "HIDDEN") definition_sequence
public_clause: ("PUBLIC" | "DEFINE" | "LIBRA") definition_sequence
// definition_sequence: definition (SEPARATOR definition)* SEPARATOR?
definition_sequence: definition (SEPARATOR definition)* SEPARATOR?
definition: NAME stack_effect? EQUALS term
stack_effect: COLON LPAREN stack_pattern ARROW stack_pattern RPAREN
stack_pattern: stack_item*
stack_item: NAME | LSQB stack_pattern RSQB

?term: (NAME | FLOAT | INTEGER | FRACTION | CHAR | STRING | LBRACE CHAR_OR_INT* RBRACE | LSQB term RSQB)*

// COMMENTS
COMMENT.11: /#[^\r\n]*/
MULTILINE_COMMENT.11: /\(\*.*?\*\)/s

// TOKENS
END.9: "END"
DOT.9: /\.(?![A-Za-z0-9!+\-=<>_,?.])/
SEPARATOR: ";"
STRING.8: /"(?:[^"\\]|\\.)*"/
FLOAT.8: /-?(?:\d+\.\d+)(?:[eE][+-]?\d+)?/
INTEGER.8: /-?\d+/
FRACTION.8: /-?\d+⁄-?\d+/
CHAR.8: /'(?:[^'\[\]\{\}\;\.$\s]+)/
CHAR_OR_INT: (CHAR | INTEGER)
EQUALS: "=="
COLON: ":"
ARROW: "--"
LPAREN: "("
RPAREN: ")"
LSQB: "["
RSQB: "]"
LBRACE: "{"
RBRACE: "}"
NAME: /[^\s\[\]\\(\){\}\;\.\#](?:[A-Za-z0-9!+\-=<>_,?.]*[A-Za-z0-9!+\-=<>_,?])?/

// WHITESPACE
%import common.WS
%ignore WS
%ignore COMMENT
%ignore MULTILINE_COMMENT
"""

import lark

def parse(source: str, start='start', filename=None):
    parser = lark.Lark(GRAMMAR, start=start, parser="lalr", lexer="contextual", propagate_positions=True)

    def _flatten(node):
        if isinstance(node, lark.Tree):
            if node.data == 'stack_effect': return  # documentation only for now
            for child in node.children:
                yield from _flatten(child)
        elif node.type not in ('SEPARATOR', 'COLON', 'LPAREN', 'RPAREN', 'ARROW'):
            meta = {'filename': filename, 'lines': (node.line, node.end_line),
                    'columns': (node.column, node.end_column)} if hasattr(node, 'line') else {}
            yield (node.type, node.value, meta)

    def _traverse(it):
        if isinstance(it, lark.Token):
            if it.type not in ('DOT', 'END'):
                yield 'term', [(it.type, it.value, {'filename': filename})]
            return
        assert isinstance(it, lark.Tree)

        if it.data == 'library':
            sections = {"module": None, "private": [], "public": []}
            for ch in [c for c in it.children[:-1] if c not in ('END', '.')]:
                key = ch.data.split('_', maxsplit=1)[0]
                if key != 'module':
                    sections[key] = [(toks[0], toks[2:]) for i in ch.children[0].children if (toks := list(_flatten(i)))]
            yield 'library', sections
        elif it.data == 'term':
            yield 'term', list(_flatten(it))
        else:
            for ch in it.children:
                yield from _traverse(ch)

    tree = parser.parse(source)
    yield from _traverse(tree)

def load_source_lines(meta, keyword, line):
    if meta['filename'] is None or not os.path.isfile(meta['filename']): return ""
    source = open(meta['filename'], 'r').read()
    lines = [l for l in source.split('\n')[meta['start']-1:meta['finish']]]
    j = line - meta['start']
    lines[j] = lines[j].replace(keyword, f"\033[48;5;30m\033[1;97m{keyword}\033[0m")
    return '\n'.join(lines)

def print_source_lines(op, lib, file=sys.stderr):
    def _contained_in(k, prg):
        if isinstance(prg, list): return any(_contained_in(k, p) for p in prg)
        return id(op) == id(prg)

    src = [(meta, k) for k, (prog, meta) in lib.items() if _contained_in(k, prog)]
    for meta, ctx in src + [(op.meta, '')]:
        print(f"\033[97m  File \"{meta['filename']}\", lines {meta['start']}-{meta['finish']}, in {ctx}\033[0m", file=file)
        if (lines := load_source_lines(meta, keyword=op.name, line=op.meta['start'])):
            print(textwrap.indent(textwrap.dedent(lines), prefix='    '), sep='\n', end='\n\n', file=file)
        break

def format_parse_error_context(filename, line, column, token_value, source=None):
    lines = source.splitlines(keepends=True) if source else open(filename, 'r').readlines()
    start_line, end_line = max(0, line - 3), min(len(lines), line + 2)
    result = [f"\033[97m  File \"{filename}\", line {line}\033[0m"]

    for i in range(start_line, end_line):
        line_content = lines[i].rstrip('\n')
        line_color = '\033[90m'
        if i+1 == line:
            line_color = '\033[97m'
            if column > 0 and column <= len(line_content):
                line_content = (
                    line_content[:column-1] + 
                    f"\033[48;5;30m\033[1;97m{line_content[column-1:column+len(token_value)-1]}\033[0m" +
                    line_content[column+len(token_value)-1:]
                )
        result.append(f"{line_color}{i+1:>5} |\033[0m {line_content}")
    return '\n' + '\n'.join(result) + '\n'


def compile_body(tokens: list, library={}, meta={}):
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
            exc = NameError(f"Unknown instruction `{token}`.")
            exc.token = token
            raise exc

    assert len(stack) == 0
    return output, meta


_FUNCTION_ALIASES = {
    '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'rem',
    '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte',
    '=': 'equal?', '!=': 'differ?', 'size': 'length',
}

def FUNC(x, meta={}):
    x = _FUNCTION_ALIASES.get(x, x)
    if x not in FUNCTIONS:
        op_fns = {k: v for k, v in globals().items() if k.startswith('op_')}
        _name = 'op_'+x.replace('-', '_').replace('!', '_b').replace('?', '_q')
        FUNCTIONS[x] = _make_wrapper(op_fns[_name], x) if _name in op_fns else None
    if (fn := FUNCTIONS[x]) is None: return None
    return Operation(Operation.FUNCTION, fn, x, meta)

def COMB(x, meta={}):
    return Operation(Operation.COMBINATOR, COMBINATORS[x], x, meta)

def EXEC(x, prg, meta={}):
    return Operation(Operation.EXECUTE, prg, x, meta)


_FUNCTION_SIGNATURES = {}

def _normalize_expected_type(tp):
    if tp is inspect._empty: assert False
    if tp is Any: return Any
    if isinstance(tp, TypeVar): return tp
    return tp if isinstance(tp, (type, tuple, UnionType)) else 'UNK'

def get_stack_effects(fn: Callable, name: str | None = None) -> dict:
    if name in _FUNCTION_SIGNATURES:
        return _FUNCTION_SIGNATURES[name]

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    positional = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]

    ret_ann = sig.return_annotation
    returns_none = (ret_ann is inspect.Signature.empty or ret_ann is type(None) or ret_ann is None)
    returns_tuple = (ret_ann is tuple or get_origin(ret_ann) is tuple)

    if returns_none:
        outputs: list = []
    else:
        ret_ann = get_args(ret_ann) if returns_tuple else (ret_ann,)
        outputs = [_normalize_expected_type(t) for t in ret_ann]
    replace_stack = name in {'unstack'}  # Single exception allowed to do this.

    meta = {
        'arity': -1 if (has_varargs and len(positional) == 0) else len(positional),
        'valency': -1 if replace_stack else (0 if returns_none else (len(outputs) if returns_tuple else 1)),
        'inputs': list(reversed([_normalize_expected_type(p.annotation) for p in positional])),
        'outputs': list(reversed(outputs)),
    }
    _FUNCTION_SIGNATURES[name] = meta
    return meta

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

    eff = get_stack_effects(None, op.name)
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


def _make_wrapper(fn: Callable, name) -> Callable:
    meta = get_stack_effects(fn, name)
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


def execute(source: str, globals_={}, filename=None, verbosity=0, validate=False, stats=None):
    locals_ = globals_.copy()
    def _link_body(n):
        if isinstance(n, list): return [_link_body(t) for t in n]
        if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
        return n

    out = None
    for typ, data in parse(source, filename=filename):
        if typ == 'term':
            prg, _ = compile_body(data, library=locals_, meta={'filename': filename, 'lines': (2^32, -1)})
            out = interpret(prg, library=locals_, verbosity=verbosity, validate=validate, stats=stats)
            if out is False: return None, locals_
        elif typ == 'library':
            for name, tokens in data['public']:
                locals_[name[1]] = None
                prg, meta = compile_body(tokens, library=locals_, meta=name[2])
                locals_[name[1]] = (_link_body(prg), meta)
            out = tuple()
    return out, locals_


@click.command()
@click.argument('files', nargs=-1, type=click.File('r'))
@click.option('--command', '-c', 'commands', multiple=True, type=str, help='Execute Joy code from command line.')
@click.option('--repl', is_flag=True, help='Start REPL after executing commands and files.')
@click.option('--verbose', '-v', default=0, count=True, help='Enable verbose interpreter execution.')
@click.option('--validate', is_flag=True, help='Enable type and stack validation before each operation.')
@click.option('--ignore', '-i', is_flag=True, help='Ignore errors and continue executing.')
@click.option('--stats', is_flag=True, help='Display execution statistics (e.g., number of steps).')
@click.option('--plain', '-p', is_flag=True, help='Strip ANSI color codes and redirect stderr to stdout.')
def main(files: tuple, commands: tuple, repl: bool, verbose: int, validate: bool, ignore: bool, stats: bool, plain: bool):

    if plain is True:
        writer = _write_without_ansi(sys.stdout.write)
        sys.stdout.write, sys.stderr.write = writer, writer
    failure = False

    def _maybe_fatal_error(message: str, detail: str, exc_type: str = None, context: str = '', is_repl=False):
        header = detail if not exc_type else f"{detail} (Exception: \033[33m{exc_type}\033[0m)"
        print(f'\033[30;43m {message} \033[0m {header}\n{context}', file=sys.stderr)
        if not is_repl and not ignore: sys.exit(1)

    def _handle_exception(exc, filename, source, is_repl=False):
        if isinstance(exc, lark.exceptions.ParseError):
            if is_repl and "Unexpected token Token('$END', '')" in str(exc): return True
            context = format_parse_error_context(filename, exc.line, exc.column, exc.token.value, source=source)
            context += f"\n\033[90m{str(exc).replace(chr(10), ' ').replace(chr(9), ' ')}\033[0m\n"
            _maybe_fatal_error("SYNTAX ERROR.", f"Parsing `\033[97m{filename}\033[0m` caused a problem!", type(exc).__name__, context, is_repl)
        elif isinstance(exc, NameError) and hasattr(exc, 'token'):
            _maybe_fatal_error("LINKER ERROR.", f"Term `\033[1;97m{exc.token}\033[0m` from `\033[97m{filename}\033[0m` was not found in library!", type(exc).__name__, '', is_repl)
        elif isinstance(exc, Exception):
            detail = f"Execution failed: {exc}" if is_repl else f"Source `\033[97m{filename}\033[0m` failed during execution!\n{traceback.format_exc()}"
            _maybe_fatal_error("UNKNOWN ERROR." if not is_repl else "ERROR.", detail, None, '', is_repl)
            if is_repl and verbose > 0: traceback.print_exc()
        return False

    _, globals_ = execute(open('libs/stdlib.joy', 'r', encoding='utf-8').read(), filename='libs/stdlib.joy', validate=validate)

    # Build execution list: files first, then commands.
    items = [(f.read(), f.name) for f in files]
    items += [(cmd, f'<INPUT_{i+1}>') for i, cmd in enumerate(commands)]

    total_stats = {'steps': 0, 'start': time.time()} if stats else None
    for source, filename in items:
        try:
            r, globals_ = execute(source, globals_=globals_, filename=filename, verbosity=verbose, validate=validate, stats=total_stats)
            (r is None and ((failure := True) or (not ignore and sys.exit(1))))
        except (NameError, lark.exceptions.ParseError, Exception) as exc:
            _handle_exception(exc, filename, source, is_repl=False)

    if total_stats and len(items) > 0:
        elapsed_time = time.time() - total_stats['start']
        print(f"\n\033[97m\033[48;5;30m STATISTICS. \033[0m")
        print(f"step\t\033[97m{total_stats['steps']:,}\033[0m")
        print(f"time\t\033[97m{elapsed_time:.3f}s\033[0m")

    # Start REPL if no items were provided or --repl flag was set
    if len(items) == 0 or repl:
        print('joyfl - Functional stack language REPL; type Ctrl+C to exit.')
        source = ""

        while True:
            try:
                prompt = "\033[36m<<< \033[0m" if not source.strip() else "\033[36m... \033[0m"
                line = input(prompt)
                if len(line.strip()) == 0: continue
                if line.strip() in ('quit', 'exit'): break
                source += line + " "

                try:
                    stack, globals_ = execute(source, globals_=globals_, filename='<REPL>', verbosity=verbose, validate=validate)
                    if stack: print("\033[90m>>>\033[0m", _format_item(stack[-1]))
                    source = ""
                except (NameError, lark.exceptions.ParseError, Exception) as exc:
                    if not _handle_exception(exc, '<REPL>', source, is_repl=True):
                        source = ""

            except (KeyboardInterrupt, EOFError):
                print(""); break

    sys.exit(failure)


if __name__ == "__main__":
    main()
