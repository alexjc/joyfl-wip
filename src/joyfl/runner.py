## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

from .types import Operation
from .parser import parse
from .linker import link_body
from .interpreter import interpret


def execute(source: str, globals_={}, filename=None, verbosity=0, validate=False, stats=None):
    locals_ = globals_.copy()
    def _link_body(n):
        if isinstance(n, list): return [_link_body(t) for t in n]
        if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
        return n

    out = None
    for typ, data in parse(source, filename=filename):
        if typ == 'term':
            prg, _ = link_body(data, library=locals_, meta={'filename': filename, 'lines': (2^32, -1)})
            out = interpret(prg, library=locals_, verbosity=verbosity, validate=validate, stats=stats)
            if out is False: return None, locals_
        elif typ == 'library':
            for name, tokens in data['public']:
                locals_[name[1]] = None
                prg, meta = link_body(tokens, library=locals_, meta=name[2])
                locals_[name[1]] = (_link_body(prg), meta)
            out = tuple()
    return out, locals_
