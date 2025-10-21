## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import ast
from fractions import Fraction

from .types import Operation
from .errors import JoyNameError
from .library import Library


def link_body(tokens: list, meta: dict, lib: Library):
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
        elif token in lib.combinators:
            output.append(Operation(Operation.COMBINATOR, lib.combinators[token], token, mt))
        elif token in lib.constants:
            output.append(lib.constants[token])
        elif (name := token.lstrip('@')) in lib.factories or token.startswith('@'):
            if not (factory := lib.factories.get(name)):
                raise JoyNameError(f"Unknown factory `{token}`.", token=token)
            output.append(factory())
        elif token in lib.quotations:
            prg, mt['body'] = lib.quotations[token]
            output.append(Operation(Operation.EXECUTE, prg, token, mt))
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
        elif (name := lib.aliases.get(token, token)) in lib.functions:
            output.append(Operation(Operation.FUNCTION, lib.get_function(name), name, mt))
        else:
            raise JoyNameError(f"Unknown instruction `{token}`.", token=token)

    assert len(stack) == 0
    return output, meta
