## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import math
import readline

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


def _format_item(it):
    if isinstance(it, list): return '[' + ' '.join(_format_item(i) for i in it) + ']'
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

    def __init__(self, type, ptr, name):
        self.type = type
        self.ptr = ptr
        self.name = name

    def __eq__(self, other):
        return self.type == other.type and self.ptr == other.ptr

    def __repr__(self):
        return f"{self.name}"

def FUNC(x):
    return Operation(Operation.FUNCTION, FUNCTIONS[x], x)
def COMB(x):
    return Operation(Operation.COMBINATOR, COMBINATORS[x], x)
def EXEC(x):
    return Operation(Operation.EXECUTE, None, x)


def comb_i(queue, tail, head, library={}):
    """Takes a program as quotation on the top of the stack, and puts it into the queue for execution."""
    assert isinstance(head, list)
    queue[0:0] = head
    return tail

def comb_dip(queue, *stack, library={}):
    """Schedules a program for execution like `i`, but removes the second top-most item from the stack too
    and then restores it after the program is done.  This is like running `i` one level lower in the stack.
    """
    ((tail, item), head) = stack
    assert isinstance(head, list)
    queue[0:0] = head + [item]
    return tail

def comb_step(queue, *stack, library={}):
    """Applies a program to every item in a list in a recursive fashion.  `step` expands into another
    quotation that includes itself to run on the rest of the list, after the program was applied to the
    head of the list.
    """
    (tail, values), program = stack
    assert isinstance(program, list) and isinstance(values, list)
    if len(values) == 0: return tail
    queue[0:0] = [values[0]] + program + [values[1:], program, COMB('step')]
    return tail

def comb_cont(queue, *stack, library={}):
    print(f"\033[97m  ~ :\033[0m  ", end=''); show_stack(stack, width=72, end='')
    try:
        program = []
        value = input("\033[4 q\033[36m  ...  \033[0m")
        if value.strip():
            for typ, data in parse(value, start='term'):
                program = compile_body(data, library)
    except Exception as e:
        print('EXCEPTION: comb_cont could not parse or compile the text.', e)
        import traceback; traceback.print_exc(limit=2)
    finally:
        print("\033[0 q", end='')

    if program:
        queue[0:0] = program + [COMB(',,,')]
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
    'pop': lambda t, h: t,
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
    'put': lambda t, h: print(_format_item(h)) or t,
    'assert': lambda _, h: _assert(h),
    'raise': lambda _, h: _raise(h),
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

def _flatten(node):
    tokens = []
    if isinstance(node, lark.Tree):
        for child in node.children:
            tokens.extend(_flatten(child))
    elif node.type != 'SEPARATOR':
        tokens.append(node)
    return tokens

def parse(source: str, start='start'):
    parser = lark.Lark(GRAMMAR, start=start, parser="lalr", lexer="contextual")

    def _traverse(it):
        if isinstance(it, lark.Token):
            if it.type not in ('DOT', 'END'):
                yield 'term', [(it.type, it.value)]
            return
        assert isinstance(it, lark.Tree)

        if it.data == 'library':
            sections = {"module": [], "private": [], "public": []}
            for ch in [c for c in it.children[:-1] if c not in ('END', '.')]:
                key = ch.data.split('_', maxsplit=1)[0]
                if key != 'module':
                    sections[key] = [(toks[0], toks[2:]) for i in ch.children[0].children if (toks := _flatten(i))]
            yield 'library', sections
        elif it.data == 'term':
            flattened = _flatten(it)
            yield 'term', [(token.type, token.value) for token in flattened]
        else:
            for ch in it.children:
                yield from _traverse(ch)

    tree = parser.parse(source)
    yield from _traverse(tree)

def compile_body(tokens: list, library={}):
    output = (None, [])
    for typ, token in tokens:
        if token == '[':
            output = (output, [])
        elif token == ']':
            output, head = output
            output[-1].append(head)
        elif token in COMBINATORS:
            output[-1].append(Operation(Operation.COMBINATOR, COMBINATORS[token], token))
        elif token in FUNCTIONS:
            output[-1].append(Operation(Operation.FUNCTION, FUNCTIONS[token], token))
        elif token in library:
            output[-1].append(Operation(Operation.EXECUTE, library[token], token))
        elif token.startswith('"') and token.endswith('"'):
            output[-1].append(str(token.strip('"')))
        elif token.startswith("'"):
            output[-1].append(bytes(token[1:], encoding='utf-8'))
        elif token.isdigit() or token[0] == '-' and token[1:].isdigit():
            output[-1].append(int(token))
        elif len(token) > 1 and token.count('.') == 1 and token.count('-') <= 1 and token.lstrip('-').replace('.', '').isdigit():
            output[-1].append(float(token))
        elif token in CONSTANTS:
            output[-1].append(CONSTANTS[token])
        else:
            exc = NameError(f"Unknown instruction `{token}`.")
            exc.token = token
            raise exc

    assert output[-1] is not None
    return output[-1]


def interpret(program: list, stack=None, library={}, verbosity=0):
    stack = tuple() if stack is None else stack
    def is_notable(op):
        if not isinstance(op, Operation): return False
        return isinstance(op.ptr, list) or op.type == Operation.COMBINATOR

    step = 0
    while program:
        if verbosity == 2 or (verbosity == 1 and (is_notable(program[0]) or step == 0)):
            print(f"\033[90m{step:>3} :\033[0m  ", end='')
            show_program_and_stack(program, stack)

        step += 1
        op = program.pop(0)
        if isinstance(op, bytes) and op in (b'ABORT', b'BREAK'):
            print(f"\033[97m  ~ :\033[0m  ", end=''); show_program_and_stack(program, stack)
            if op == b'ABORT': import sys; sys.exit(-1)
            if op == b'BREAK': input(); continue

        if not isinstance(op, Operation):
            stack = (stack, op)
            continue

        match op.type:
            case Operation.FUNCTION:
                try:
                    stack = op.ptr(*stack)
                except:
                    print(f'EXCEPTION: Function {op} caused an error in interpreter.'); show_program_and_stack(program, stack); print()
                    import traceback; traceback.print_exc(limit=2)
                    raise
            case Operation.COMBINATOR:
                stack = op.ptr(program, *stack, library=library)
            case Operation.EXECUTE:
                prg = op.ptr if op.ptr is not None else library[op.name]
                program[0:0] = prg

    if verbosity > 0:
        print(f"\033[90m{step:>3} :\033[0m  ", end='')
        show_program_and_stack(program, stack)

    return stack


def execute(source: str, globals_={}, verbosity=0):
    locals_ = globals_.copy()
    def _link_body(n):
        if isinstance(n, list): return [_link_body(t) for t in n]
        if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
        return n

    out = None
    for typ, data in parse(source):
        if typ == 'term':
            prg = compile_body(data, library=locals_)
            out = interpret(prg, library=locals_, verbosity=verbosity)
        elif typ == 'library':
            for name, tokens in data['public']:
                locals_[name] = None
                prg = compile_body([(t.type, t.value) for t in tokens], library=locals_)
                locals_[name] = _link_body(prg)
            out = tuple()

    return out, locals_


@click.command()
@click.argument('files', nargs=-1)
@click.option('--verbose', '-v', default=0, count=True, help='Enable verbose interpreter execution.')
def main(files: tuple, verbose: int):
    _, globals_ = execute(open('libs/stdlib.joy', 'r', encoding='utf-8').read())

    # Execute each provided file one by one. They are not imported into the globals.
    for file_path in files:
        if file_path == 'repl': continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            execute(source, globals_=globals_, verbosity=verbose)
        except NameError as e:
            if hasattr(e, 'token') and e.token not in r'{}':
                print(f"NameError: term not found `{e.token}`.")
        except Exception as e:
            print(f'Exception in {file_path}!')
            import traceback; traceback.print_exc()

    if len(files) == 0 or files[0] == 'repl':
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
                    print('ERROR: Parser raised an exception:', exc)
                    source = ""

            except (KeyboardInterrupt, EOFError):
                print(""); break


if __name__ == "__main__":
    main()
