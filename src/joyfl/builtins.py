## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from . import operators
from . import combinators as C
from .library import Library


def _joy_name_from_python(py_name: str) -> str:
    # py_name like 'op_equal_q' -> 'equal?'; 'op_put_b' -> 'put!'; underscores -> dashes
    base = py_name[3:]
    base = base.replace('_q', '?').replace('_b', '!')
    return base.replace('_', '-')


def load_builtins_library():
    # Combinators
    combinators = {
        'i': C.comb_i,
        'dip': C.comb_dip,
        'step': C.comb_step,
        '...': C.comb_cont,
        'exec!': C.comb_exec_b,
        'struct': C.comb_struct,
        'destruct': C.comb_destruct,
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
