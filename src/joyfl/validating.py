## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import inspect
from types import UnionType
from typing import Any, TypeVar, Callable, get_origin, get_args


_FUNCTION_SIGNATURES = {}

def _normalize_expected_type(tp):
    if tp is inspect._empty: assert False
    if tp is Any: return Any
    if isinstance(tp, TypeVar): return tp
    return tp if isinstance(tp, (type, tuple, UnionType)) else 'UNK'

def get_stack_effects(*, fn: Callable = None, name: str = None) -> dict:
    if name in _FUNCTION_SIGNATURES:
        return _FUNCTION_SIGNATURES[name]
    assert fn is not None, "Must specify the function if name is not in signature cache."

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    positional = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]

    ret_ann = sig.return_annotation
    returns_none = (ret_ann is inspect.Signature.empty or ret_ann is type(None) or ret_ann is None)
    returns_tuple = (ret_ann is tuple or get_origin(ret_ann) is tuple)

    if returns_none:
        outputs: list = []
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
    _FUNCTION_SIGNATURES[name] = meta
    return meta
