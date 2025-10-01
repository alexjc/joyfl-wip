## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import sys
import math
import time
import textwrap
import readline
import traceback
import collections

import click


def stack_to_list(stack):
    result = []
    while stack:
        stack, head = stack
        result.append(head)
    return result

def list_to_stack(values, base=None):
    stack = tuple() if base is None else base
    for value in reversed(values):
        stack = (stack, value)
    return stack


def _format_item(it, width=None, indent=0):
    if isinstance(it, list):
        formatted_items = [_format_item(i, width, indent + 4) for i in it]
        single_line = '[' + ' '.join(formatted_items) + ']'
        # If it fits on one line, use single line format.
        if width is None or len(single_line) + indent <= width:
            return single_line
        # Otherwise use multi-line format...
        result = '[   '
        for i, item in enumerate(formatted_items):
            if i > 0: result += '\n' + (' ' * (indent + 4))
            result += item
        result += '\n' + (' ' * indent) + ']'
        return result
    
    if isinstance(it, bool): return str(it).lower()
    if isinstance(it, bytes): return str(it)[1:-1]
    return str(it)

def show_stack(stack, width=72, end='\n'):
    stack_str = ' '.join(_format_item(s) for s in reversed(stack_to_list(stack))) if stack else '∅'
    if len(stack_str) > width:
        stack_str = '… ' + stack_str[-width+2:]
    print(f"{stack_str:>{width}}", end=end)

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
        return self.type == other.type and self.ptr == other.ptr

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
                program, _ = compile_body(data, library, meta={'filename': '<repl>', 'lines': (1, 1)})
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
    '+': lambda t, h: (t[0], t[1] + h),
    '-': lambda t, h: (t[0], t[1] - h),
    'neg': lambda t, h: (t, -h),
    'abs': lambda t, h: (t, abs(h)),
    'sign': lambda t, h: (t, (h > 0) - (h < 0)),
    'min': lambda t, h: (t[0], min(t[1], h)),
    'max': lambda t, h: (t[0], max(t[1], h)),
    'square': lambda t, h: (t, h*h),
    '*': lambda t, h: (t[0], t[1] * h),
    '/': lambda t, h: (t[0], t[1] // h),
    '%': lambda t, h: (t[0], t[1] % h),
        'rem': lambda t, h: (t[0], t[1] % h),
    # BOOLEAN LOGIC
    '=': lambda t, h: (t[0], t[1] == h),
        'equal?': lambda t, h: (t[0], t[1] == h),
    '!=': lambda t, h: (t[0], t[1] != h),
    '>': lambda t, h: (t[0], t[1] > h),
    '>=': lambda t, h: (t[0], t[1] >= h),
    '<': lambda t, h: (t[0], t[1] < h),
    '<=': lambda t, h: (t[0], t[1] <= h),
    'and': lambda t, h: (t[0], t[1] and h),
    'or': lambda t, h: (t[0], t[1] or h),
    'not': lambda t, h: (t, not h),
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
    'pop': lambda t, _: t,
    'dup': lambda t, h: ((t, h), h),
    'cons': lambda t, h: (t[0], [t[1]]+h),
    'append': lambda t, h: (t[0], h+[t[1]]),
    'drop': lambda t, h: (t[0], [x for x in t[1] if x != h]),
    'take': lambda t, h: (t[0], t[1][:h]),
    'uncons': lambda t, h: ((t, h[0]), h[1:]),
    'swap': lambda t, h: ((t[0], h), t[1]),
    # STACK MANIPULATION
    'stack': lambda *s: (s, stack_to_list(s)),
    'unstack': lambda _, h: list_to_stack(h),
    # INPUT / OUTPUT
    'id': lambda *s: s,
    'put!': lambda t, h: print('\033[97m' + _format_item(h, width=120) + '\033[0m') or t,
    'assert!': lambda t, h: _assert(h) or t,
    'raise!': lambda t, h: _raise(h) or t,
    # LIST OPERATIONS
    'concat': lambda t, h: (t[0], t[1] + h),
    'reverse': lambda t, h: (t, list(reversed(h))),
    'first': lambda t, h: (t, h[0]),
    'rest': lambda t, h: (t, h[1:]),
    'last': lambda t, h: (t, h[-1]),
    'index': lambda t, h: (t[0], h[t[1]]),
    'member?': lambda t, h: (t[0], t[1] in h),
    'sum': lambda t, h: (t, sum(h)),
    'length': lambda t, h: (t, len(h)),
    'product': lambda t, h: (t, math.prod(h)),
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
definition: NAME EQUALS term

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
            for child in node.children:
                yield from _flatten(child)
        elif node.type != 'SEPARATOR':
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
    source = open(meta['filename'], 'r').read()
    lines = [l for l in source.split('\n')[meta['start']-1:meta['finish']]]
    j = line - meta['start']
    lines[j] = lines[j].replace(keyword, f"\033[48;5;30m\033[1;97m{keyword}\033[0m")
    return '\n'.join(lines)

def print_source_lines(op, lib):
    def _contained_in(k, prg):
        if isinstance(prg, list): return any(_contained_in(k, p) for p in prg)
        return id(op) == id(prg)

    src = [(meta, f'in {k}') for k, (prog, meta) in lib.items() if _contained_in(k, prog)]
    for meta, ctx in src + [(op.meta, '')]:
        print(f"\033[97m  File \"{meta['filename']}\", lines {meta['start']}-{meta['finish']}, in {ctx}\033[0m")
        lines = load_source_lines(meta, keyword=op.name, line=op.meta['start'])
        print(textwrap.indent(textwrap.dedent(lines), prefix='    '), sep='\n', end='\n\n')
        break

def format_parse_error_context(filename, line, column, token_value):
    with open(filename, 'r') as f:
        lines = f.readlines()
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
            output.append(str(token.strip('"')))
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


def interpret(program: list, stack=None, library={}, verbosity=0, stats=None):
    stack = tuple() if stack is None else stack
    program = collections.deque(program)

    def is_notable(op):
        if not isinstance(op, Operation): return False
        return isinstance(op.ptr, list) or op.type == Operation.COMBINATOR

    step = 0
    while program:
        if verbosity == 2 or (verbosity == 1 and (is_notable(program[0]) or step == 0)):
            print(f"\033[90m{step:>3} :\033[0m  ", end='')
            show_program_and_stack(program, stack)

        step += 1
        op = program.popleft()
        if isinstance(op, bytes) and op in (b'ABORT', b'BREAK'):
            print(f"\033[97m  ~ :\033[0m  ", end=''); show_program_and_stack(program, stack)
            if op == b'ABORT': sys.exit(-1)
            if op == b'BREAK': input(); continue

        if not isinstance(op, Operation):
            stack = (stack, op)
            continue

        match op.type:
            case Operation.FUNCTION:
                try:
                    stack = op.ptr(*stack)
                except AssertionError as exc:
                    print(f'\033[30;43m ASSERTION FAILED. \033[0m Function \033[1;97m`{op}`\033[0m raised an error.\n')
                    print_source_lines(op, library)
                    print(f'\033[1;33m  Stack content, step {step}, is\033[0;33m\n    ', end='')
                    show_stack(stack, width=None); print('\033[0m')
                    return False
                except Exception as exc:
                    print(f'\033[30;43m RUNTIME ERROR. \033[0m Function \033[1;97m`{op}`\033[0m caused an error in interpret! (Exception: \033[33m{type(exc).__name__}\033[0m)\n')
                    tb_lines = traceback.format_exc().split('\n')
                    print(*[line for line in tb_lines if 'lambda' in line], sep='\n', end='\n')
                    print_source_lines(op, library)
                    return False
            case Operation.COMBINATOR:
                stack = op.ptr(op, program, *stack, library=library)
            case Operation.EXECUTE:
                program.extendleft(reversed(op.ptr))

    if verbosity > 0:
        print(f"\033[90m{step:>3} :\033[0m  ", end='')
        show_program_and_stack(program, stack)
    if stats is not None:
        stats['steps'] = stats.get('steps', 0) + step

    return stack


def execute(source: str, globals_={}, filename=None, verbosity=0, stats=None):
    locals_ = globals_.copy()
    def _link_body(n):
        if isinstance(n, list): return [_link_body(t) for t in n]
        if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
        return n

    out = None
    for typ, data in parse(source, filename=filename):
        if typ == 'term':
            prg, _ = compile_body(data, library=locals_, meta={'filename': filename, 'lines': (2^32, -1)})
            out = interpret(prg, library=locals_, verbosity=verbosity, stats=stats)
            if out is False: return None, {}
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
@click.option('--ignore', '-i', is_flag=True, help='Ignore errors and continue executing.')
@click.option('--stats', is_flag=True, help='Display execution statistics (e.g., number of steps).')
def main(files: tuple, commands: tuple, repl: bool, verbose: int, ignore: bool, stats: bool):
    
    def _fatal_error(message: str, detail: str, exc_type: str = None, context: str = ''):
        header = detail if not exc_type else f"{detail} (Exception: \033[33m{exc_type}\033[0m)"
        print(f'\033[30;43m {message} \033[0m {header}\n{context}')
        if not ignore: sys.exit(1)
    
    _, globals_ = execute(open('libs/stdlib.joy', 'r', encoding='utf-8').read(), filename='libs/stdlib.joy')

    # Build execution list: files first, then commands.
    items = [(f.read(), f.name) for f in files]
    items += [(cmd, f'<INPUT_{i+1}>') for i, cmd in enumerate(commands)]

    total_stats = {'steps': 0, 'start': time.time()} if stats else None
    for source, filename in items:
        try:
            r, globals_ = execute(source, globals_=globals_, filename=filename, verbosity=verbose, stats=total_stats)

        except NameError as exc:
            if hasattr(exc, 'token'):
                detail = f"Term `\033[1;97m{exc.token}\033[0m` from `\033[97m{filename}\033[0m` was not found in library!"
                _fatal_error("LINKER ERROR.", detail, type(exc).__name__)

        except lark.exceptions.ParseError as exc:
            context = format_parse_error_context(filename, exc.line, exc.column, exc.token.value)
            context += f"\n\033[90m{str(exc).replace(chr(10), ' ').replace(chr(9), ' ')}\033[0m\n"
            _fatal_error("SYNTAX ERROR.", f"Parsing `\033[97m{filename}\033[0m` caused a problem!", type(exc).__name__, context=context)

        except Exception as exc:
            tb = traceback.format_exc()
            detail = f"Source `\033[97m{filename}\033[0m` failed during execution!\n{tb}"
            _fatal_error("UNKNOWN ERROR.", detail)

    # Display statistics if requested
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
                    stack, globals_ = execute(source, globals_=globals_, verbosity=verbose)
                    if stack: print("\033[90m>>>\033[0m", _format_item(stack[-1]))
                    source = ""
                except lark.exceptions.ParseError as exc:
                    if "Unexpected token Token('$END', '')" in str(exc):
                        continue
                    print(f'\033[30;43m SYNTAX  \033[0m Input caused a problem in the parser! (Exception: \033[33m{type(exc).__name__}\033[0m)\n')
                    source = ""

            except (KeyboardInterrupt, EOFError):
                print(""); break


if __name__ == "__main__":
    main()
