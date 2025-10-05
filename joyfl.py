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

import click


class stack(list): pass


def stack_to_list(stk):
    result = []
    while stk:
        stk, head = stk
        result.append(head)
    return stack(result)

def list_to_stack(values, base=None):
    stack = tuple() if base is None else base
    for value in reversed(values):
        stack = (stack, value)
    return stack


def _write_without_ansi(write_fn):
    """Wrapper function that strips ANSI codes before calling the original writer."""
    ansi_re = re.compile(r'\033\[[0-9;]*m')
    return lambda text: write_fn(ansi_re.sub('', text))

def _format_item(it, width=None, indent=0):
    if (is_stack := isinstance(it, stack)) or isinstance(it, list):
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

def FUNC(x, meta={}):
    return Operation(Operation.FUNCTION, FUNCTIONS[x], x, meta)
def COMB(x, meta={}):
    return Operation(Operation.COMBINATOR, COMBINATORS[x], x, meta)
def EXEC(x, prg, meta={}):
    return Operation(Operation.EXECUTE, prg, x, meta)


def comb_i(_, queue, tail, head, library={}):
    """Takes a program as quotation on the top of the stack, and puts it into the queue for execution."""
    assert isinstance(head, list)
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

def _assert(x): assert x
def _raise(x): raise x

# lamba TAIL, HEAD: (NEW_TAIL, NEW_HEAD)
FUNCTIONS = { 
    # ARITHMETIC
    '+': lambda tI, hI: (tI[0], tI[1] + hI),
    '-': lambda tI, hI: (tI[0], tI[1] - hI),
    'neg': lambda t, hI: (t, -hI),
    'abs': lambda t, hI: (t, abs(hI)),
    'sign': lambda t, hI: (t, (hI > 0) - (hI < 0)),
    'min': lambda tI, hI: (tI[0], min(tI[1], hI)),
    'max': lambda tI, hI: (tI[0], max(tI[1], hI)),
    'square': lambda t, hI: (t, hI*hI),
    '*': lambda tI, hI: (tI[0], tI[1] * hI),
    '/': lambda tI, hI: (tI[0], tI[1] // hI),
    '%': lambda tI, hI: (tI[0], tI[1] % hI),
        'rem': lambda tI, hI: (tI[0], tI[1] % hI),
    # BOOLEAN LOGIC
    '=': lambda t, h: (t[0], t[1] == h),
        'equal?': lambda t, h: (t[0], t[1] == h),
    '!=': lambda t, h: (t[0], t[1] != h),
    '>': lambda tI, hI: (tI[0], tI[1] > hI),
    '>=': lambda tI, hI: (tI[0], tI[1] >= hI),
    '<': lambda tI, hI: (tI[0], tI[1] < hI),
    '<=': lambda tI, hI: (tI[0], tI[1] <= hI),
    'and': lambda tB, hB: (tB[0], tB[1] and hB),
    'or': lambda tB, hB: (tB[0], tB[1] or hB),
    'not': lambda t, hB: (t, not hB),
    'xor': lambda t, h: (t[0], t[1] ^ h),
    # DATA & INTROSPECTION
    'null?': lambda t, h: (t, (len(h) if isinstance(h, (list, str)) else h) == 0),
    'small?': lambda t, h: (t, (len(h) if isinstance(h, (list, str)) else h) < 2),
    'sametype?': lambda t, h: (t[0], type(t[1]) == type(h)),
    'integer?': lambda t, h: (t, isinstance(h, int)),
    'float?': lambda t, h: (t, isinstance(h, float)),
    'list?': lambda t, h: (t, isinstance(h, list)),
    'string?': lambda t, h: (t, isinstance(h, str)),
    'boolean?': lambda t, h: (t, isinstance(h, bool)),
    # LIST MANIPULATION
    'cons': lambda tA, hL: (tA[0], [tA[1]]+hL),
    'append': lambda tA, hL: (tA[0], hL+[tA[1]]),
    'remove': lambda tL, h: (tL[0], [x for x in tL[1] if x != h]),
    'take': lambda tL, hI: (tL[0], tL[1][:hI]),
    'drop': lambda tL, hI: (tL[0], tL[1][hI:]),
    'size': lambda t, hL: (t, len(hL)),
    'uncons': lambda t, hL: ((t, hL[0]), hL[1:]),
    'swap': lambda tA, hA: ((tA[0], hA), tA[1]),
    # STACK MANIPULATION
    'pop': lambda t, _: t,
    'dup': lambda t, h: ((t, h), h),
    'stack': lambda *s: (s, stack_to_list(s)),
    'unstack': lambda _, h: list_to_stack(h),
    'stack-size': lambda *s: (s, len(stack_to_list(s))),
    # INPUT / OUTPUT
    'id': lambda *s: s,
    'put!': lambda t, h: print('\033[97m' + _format_item(h, width=120) + '\033[0m') or t,
    'assert!': lambda t, hB: _assert(hB) or t,
    'raise!': lambda t, h: _raise(h) or t,
    # STRING MANIPULATION
    'str-concat': lambda tS, hS: (tS[0], str(tS[1]) + str(hS)),
    'str-match?': lambda tS, hS: (tS[0], str(tS[1]) in str(hS)),
    'str-split': lambda tS, hS: (tS[0], hS.split(tS[1]) if isinstance(hS, str) else hS),
    # LIST OPERATIONS
    'concat': lambda tL, hL: (tL[0], tL[1] + hL),
    'reverse': lambda t, hL: (t, list(reversed(hL))),
    'first': lambda t, hL: (t, hL[0]),
    'rest': lambda t, hL: (t, hL[1:]),
    'last': lambda t, hL: (t, hL[-1]),
    'index': lambda tI, hL: (tI[0], hL[int(tI[1])]),
    'member?': lambda t, hL: (t[0], t[1] in hL),
    'sum': lambda t, hL: (t, sum(hL)),
    'length': lambda t, h: (t, len(h)),  # polymorphic: works on lists, strings, etc.
    'product': lambda t, hL: (t, math.prod(hL)),
}

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

?term: (NAME | FLOAT | INTEGER | CHAR | STRING | LBRACE CHAR_OR_INT* RBRACE | LSQB term RSQB)*

// COMMENTS
COMMENT.11: "#" /[^\r\n]*/
MULTILINE_COMMENT.11: /\(\*.*?\*\)/s

// TOKENS
END.9: "END"
DOT.9: "."
SEPARATOR: ";"
STRING.8: /"(?:[^"\\]|\\.)*"/  
FLOAT.8: /-?(?:\d+\.\d+)(?:[eE][+-]?\d+)?/
INTEGER.8: /-?\d+/
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
NAME: /[^\s\[\]\\(\){\}\;\.#][A-Za-z0-9!+\-=<>_,?]*/

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

    src = [(meta, f'in {k}') for k, (prog, meta) in lib.items() if _contained_in(k, prog)]
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
        elif token in FUNCTIONS:
            output.append(FUNC(token, mt))
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
        elif token.isdigit() or token[0] == '-' and token[1:].isdigit():
            output.append(int(token))
        elif len(token) > 1 and token.count('.') == 1 and token.count('-') <= 1 and token.lstrip('-').replace('.', '').isdigit():
            output.append(float(token))
        elif token in CONSTANTS:
            output.append(CONSTANTS[token])
        else:
            exc = NameError(f"Unknown instruction `{token}`.")
            exc.token = token
            raise exc

    assert len(stack) == 0
    return output, meta


_FUNCTION_SIGNATURES = {}

def can_execute(op: Operation, stack: tuple, library={}) -> tuple[bool, str]:
    """Check if operations can execute on stack. Only built-in functions currently."""
    if not stack or stack == tuple():
        return False, f"`{op.name}` needs at least 1 item on the stack, but stack is empty."

    tail, head = stack
    if op.name in ("i", "dip") and not isinstance(head, list):
        return False, f"`{op.name}` requires a quotation as list as top item on the stack."

    if op.type != Operation.FUNCTION: return True, ""
    if op.name not in _FUNCTION_SIGNATURES:
        sig = list(inspect.signature(op.ptr).parameters.values())
        if len(sig) == 1 and sig[0].kind == inspect.Parameter.VAR_POSITIONAL:
            _FUNCTION_SIGNATURES[op.name] = {'variadic': True}
        elif len(sig) == 2:
            tail_param, head_param = sig[0].name, sig[1].name
            needs_two_items = tail_param not in ('t', 'tail', '_') or any(c in tail_param for c in ['0', '1'])
            type_map = {'I': (int, 'int'), 'L': (list, 'list'), 'S': (str, 'str'), 'B': (bool, 'bool'), 'A': (None, 'any')}
            head_type, tail_type = None, None
            for suffix, (expected_type, type_name) in type_map.items():
                if head_param.endswith(suffix): head_type = (expected_type, type_name)
                if tail_param.endswith(suffix): tail_type = (expected_type, type_name)
            _FUNCTION_SIGNATURES[op.name] = {'needs_two_items': needs_two_items,
                                   'head_type': head_type, 'tail_type': tail_type}
        else:
            raise NotImplementedError(f"Unexpected function signature for `{op.name}`: {sig}")
    
    sig_info = _FUNCTION_SIGNATURES[op.name]
    if sig_info.get('variadic'):
        return True, ""
    # Non-variadic functions are always technically two-parameter form (tail, head).
    if sig_info['needs_two_items'] and tail == tuple():
        return False, f"`{op.name}` needs at least 2 items on the stack, but only 1 available."
    if sig_info['head_type']:
        expected_type, type_name = sig_info['head_type']
        if expected_type and not isinstance(head, expected_type):
            return False, f"`{op.name}` expects {type_name} on top of stack, got {type(head).__name__}."
    if sig_info['tail_type'] and sig_info['needs_two_items'] and len(tail) == 2:
        expected_type, type_name = sig_info['tail_type']
        if expected_type and not isinstance(tail[1], expected_type):
            return False, f"`{op.name}` expects {type_name} as second item, got {type(tail[1]).__name__}."
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
            stack = op.ptr(*stack)
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
            stack, program = interpret_step(program, stack, library)
        except AssertionError as exc:
            print(f'\033[30;43m ASSERTION FAILED. \033[0m Function \033[1;97m`{op}`\033[0m raised an error.\n', file=sys.stderr)
            print_source_lines(op, library, file=sys.stderr)
            print(f'\033[1;33m  Stack content is\033[0;33m\n    ', end='', file=sys.stderr)
            show_stack(stack, width=None, file=sys.stderr); print('\033[0m', file=sys.stderr)
            raise
        except Exception as exc:
            print(f'\033[30;43m RUNTIME ERROR. \033[0m Function \033[1;97m`{op}`\033[0m caused an error in interpret! (Exception: \033[33m{type(exc).__name__}\033[0m)\n', file=sys.stderr)
            tb_lines = traceback.format_exc().split('\n')
            print(*[line for line in tb_lines if 'lambda' in line], sep='\n', end='\n', file=sys.stderr)
            print_source_lines(op, library, file=sys.stderr)
            raise

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
