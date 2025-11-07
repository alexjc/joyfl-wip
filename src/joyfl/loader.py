## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import inspect
from types import UnionType
from typing import Any, ForwardRef, TypeVar, Callable, get_origin, get_args
from .errors import JoyNameError, JoyModuleError, JoyTypeMissing
from .types import Stack


_LIB_MODULES = {}

def get_python_name(joy_name):
    return 'op_'+joy_name.replace('-', '_').replace('!', '_b').replace('?', '_q')


def load_library_module(ns: str, meta: dict):
    if ns in _LIB_MODULES: return _LIB_MODULES[ns]

    # Default search is libs/_{ns}.py, packaged with the distribution.
    candidates = [(os.path.join(os.path.dirname(__file__), 'libs', f'_{ns}.py'), f"joyfl.libs._{ns}")]
    # Also search user specified JOY_PATH environment variable.
    candidates += [
        (os.path.join(os.path.expanduser(os.path.expandvars(base)), f'{ns}.py'), f"joyfl.ext.{ns}")
        for base in [p for p in os.environ.get('JOY_PATH', '').split(os.pathsep) if p]
    ]

    import importlib.util as importer
    for mod_path, mod_name in candidates:
        if not os.path.isfile(mod_path): continue
        spec, module = importer.spec_from_file_location(mod_name, mod_path), None
        if spec and spec.loader:
            module = importer.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except (SyntaxError, ImportError, Exception) as e:
                raise JoyModuleError(str(e), filename=mod_path, joy_op=ns, joy_meta=meta) from e
        _LIB_MODULES[ns] = module
        return module
    raise JoyModuleError(f"Module `{ns}` not found.", joy_op=ns, joy_meta=meta)


def resolve_module_op(ns: str, name: str, *, meta: dict | None = None):
    py_module = load_library_module(ns, meta=meta)
    if not (py_name := get_python_name(name)) and py_module is None: return None
    # All modules require an explicit registry of operators defined.
    for w in getattr(py_module, '__operators__', []):
        if getattr(w, '__name__', '') == py_name: return w
    raise JoyNameError(f"Operation `{py_name}` not found in library `{ns}`.", joy_op=f"{ns}.{name}", joy_meta=meta)


def _normalize_expected_type(tp):
    if tp is inspect._empty: return Any
    if tp is Any: return Any
    if isinstance(tp, TypeVar): return tp
    return tp if isinstance(tp, (type, tuple, UnionType)) else 'UNK'


def _is_stack_annotation(annotation: Any) -> bool:
    if isinstance(annotation, ForwardRef) or hasattr(annotation, '__forward_arg__'):
        annotation = annotation.__forward_arg__
    if annotation is Stack:
        return True
    if isinstance(annotation, str):
        return annotation == 'Stack' or annotation.endswith('.Stack')
    return False


def get_stack_effects(*, fn: Callable, name: str = None) -> dict:
    assert fn is not None, "Must specify the function if name is not in signature cache."

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    op_name = name or getattr(fn, '__name__', '<unnamed>')

    has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    positional = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    vararg_param = next((p for p in params if p.kind == inspect.Parameter.VAR_POSITIONAL), None)

    ret_ann = sig.return_annotation
    if ret_ann is inspect.Signature.empty:
        raise JoyTypeMissing(f"Operation `{op_name}` must declare a return annotation.")

    returns_stack_type = _is_stack_annotation(ret_ann)
    missing_inputs = [p.name for p in positional if p.annotation is inspect._empty]
    if missing_inputs:
        missing = ', '.join(missing_inputs)
        raise JoyTypeMissing(f"Operation `{op_name}` must annotate parameters: {missing}.")

    allow_variadic_stack = False
    if vararg_param is not None and vararg_param.annotation is inspect._empty:
        allow_variadic_stack = (not positional and vararg_param.name == 'stack' and returns_stack_type)
        if not allow_variadic_stack:
            raise JoyTypeMissing(f"Operation `{op_name}` requires regular type annotation for `*{vararg_param.name}`, or use variadic stack form.")

    returns_none = (ret_ann is type(None) or ret_ann is None)
    returns_tuple = (ret_ann is tuple or get_origin(ret_ann) is tuple)

    if returns_none:
        outputs: list = []
    else:
        raw_ret = get_args(ret_ann) if returns_tuple else (ret_ann,)
        outputs = [_normalize_expected_type(t) for t in raw_ret]

    replace_stack = (name in {'unstack'}) or allow_variadic_stack  # Allow stack replacement semantics.

    meta = {
        'arity': -1 if (has_varargs and len(positional) == 0) else len(positional),
        'valency': -1 if replace_stack else (0 if returns_none else (len(outputs) if returns_tuple else 1)),
        'inputs': list(reversed([_normalize_expected_type(p.annotation) for p in positional])),
        'outputs': list(reversed(outputs)),
    }
    return meta
