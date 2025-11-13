## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from .library import Library
from . import operators
from .combinators import comb_i, comb_dip, comb_step, comb_cont


def _joy_name_from_python(py_name: str) -> str:
    # py_name like 'op_equal_q' -> 'equal?'; 'op_put_b' -> 'put!'; underscores -> dashes
    base = py_name[3:]
    base = base.replace('_q', '?').replace('_b', '!')
    return base.replace('_', '-')


def load_builtins_library():
    # Combinators
    combinators = {
        'i': comb_i,
        'dip': comb_dip,
        'step': comb_step,
        '...': comb_cont,
    }
    quotations = {}
    constants = {'true': True, 'false': False}
    factories = {}
    aliases = {
        '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'rem',
        '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte',
        '=': 'equal?', '!=': 'differ?', 'size': 'length',
    }

    lib = Library(functions={}, combinators=combinators, quotations=quotations, constants=constants, factories=factories, aliases=aliases)

    # Functions (wrapped via Library helper)
    for k in dir(operators):
        if not k.startswith('op_'):
            continue
        joy = _joy_name_from_python(k)
        lib.add_function(joy, getattr(operators, k))

    lib.ensure_consistent()
    return lib
