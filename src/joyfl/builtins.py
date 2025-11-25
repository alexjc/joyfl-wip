## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from . import operators
from . import combinators as C
from .loader import get_joy_name
from .library import Library


def load_builtins_library():
    # Combinators
    combinators = {
        'i': C.comb_i,
        'dip': C.comb_dip,
        'step': C.comb_step,
        '...': C.comb_cont,
        'exec!': C.comb_exec_b,
        'struct': C.comb_struct,
        'unstruct': C.comb_unstruct,
    }
    quotations = {}
    constants = {'true': True, 'false': False}
    factories = {}
    aliases = {
        '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '//': 'idiv', '%': 'rem',
        '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte',
        '=': 'equal?', '!=': 'differ?', 'size': 'length',
    }

    lib = Library(functions={}, combinators=combinators, quotations=quotations, constants=constants, factories=factories, aliases=aliases)

    # Functions (wrapped via Library helper)
    for k in dir(operators):
        if not k.startswith('op_'): continue
        joy = get_joy_name(k)
        lib.add_function(joy, getattr(operators, k))

    lib.ensure_consistent()
    return lib
