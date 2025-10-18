## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import os


_LIB_MODULES = {}

def get_python_name(joy_name):
    return 'op_'+joy_name.replace('-', '_').replace('!', '_b').replace('?', '_q')


def load_library_module(ns: str):
    if ns in _LIB_MODULES: return _LIB_MODULES[ns]

    mod_path = os.path.join(os.path.dirname(__file__), 'libs', f'_{ns}.py')
    if not os.path.isfile(mod_path):
        _LIB_MODULES[ns] = None
        return None

    import importlib.util
    spec = importlib.util.spec_from_file_location(f"joyfl.libs._{ns}", mod_path)
    if spec is None or spec.loader is None:
        _LIB_MODULES[ns] = None
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LIB_MODULES[ns] = module
    return module


def resolve_module_op(ns: str, name: str):
    py_module = load_library_module(ns)
    if not (py_name := get_python_name(name)) and py_module is None: return None
    # All modules require an explicit registry of operators defined.
    for w in getattr(py_module, '__operators__', []):
        if getattr(w, '__name__', '') == py_name: return w
    exc = NameError(f"Operation `{py_name}` not found in library `{ns}`."); exc.token = f"{ns}.{name}"
    raise exc
