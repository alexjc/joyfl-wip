## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import os
import inspect
from types import UnionType
from typing import Any, TypeVar, Callable, get_origin, get_args
from .errors import JoyNameError


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
    raise JoyNameError(f"Operation `{py_name}` not found in library `{ns}`.", token=f"{ns}.{name}")


def _normalize_expected_type(tp):
    if tp is inspect._empty: return Any
    if tp is Any: return Any
    if isinstance(tp, TypeVar): return tp
    return tp if isinstance(tp, (type, tuple, UnionType)) else 'UNK'

def get_stack_effects(*, fn: Callable, name: str = None) -> dict:
    assert fn is not None, "Must specify the function if name is not in signature cache."

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    positional = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]

    ret_ann = sig.return_annotation
    returns_none = (ret_ann is type(None) or ret_ann is None)
    returns_tuple = (ret_ann is tuple or get_origin(ret_ann) is tuple)

    if returns_none:
        outputs: list = []
    elif ret_ann is inspect.Signature.empty:
        # No annotation: assume single return value of Any type
        outputs = [Any]
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
    return meta
