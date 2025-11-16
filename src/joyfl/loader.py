## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import inspect
from pathlib import Path
from types import UnionType
from typing import Any, ForwardRef, TypeVar, Callable, get_origin, get_args

from .types import Stack
from .errors import JoyNameError, JoyModuleError, JoyTypeMissing, JoyTypeError


_LIB_MODULES: dict[str, object] = {}


def _resolve_joy_paths() -> list[Path]:
    parts = [p for p in os.environ.get("JOY_PATH", "").split(os.pathsep) if p]
    return [Path(os.path.expanduser(os.path.expandvars(p))) for p in parts]

def get_python_name(joy_name: str) -> str:
    """Map a Joy operation name to its Python function name."""
    return 'op_'+joy_name.replace('-', '_').replace('!', '_b').replace('?', '_q')


def get_joy_name(py_name: str) -> str:
    """Inverse of `get_python_name` for well-formed operator names."""
    if not py_name.startswith("op_"):
        raise JoyModuleError(f"Operator function `{py_name}` requires prefix `op_` by convention.", joy_token=py_name, joy_meta=None)
    return py_name[3:].replace('_b', '!').replace('_q', '?').replace('_', '-')


def iter_joy_module_candidates(module_name: str):
    """Resolution order: JOY_PATHS first, then 'libs' paths relative to distribution."""
    for root in _resolve_joy_paths():
        yield root / f"{module_name}.joy"
    base = Path(__file__).resolve().parent
    for d in (base, *base.parents[:2]):
        yield d / 'libs' / f"{module_name}.joy"


def load_library_module(ns: str, meta: dict):
    if ns in _LIB_MODULES: return _LIB_MODULES[ns]

    # Search packaged libs in this package and parents; underscore-only (_{ns}.py).
    roots = (base := Path(__file__).resolve().parent, *base.parents[:2])
    candidates = [(str(d / 'libs' / f'_{ns}.py'), f"joyfl.libs._{ns}") for d in roots]

    # Also search JOY_PATH entries (plain-only {ns}.py).
    candidates += [(str(p / f'{ns}.py'), f"joyfl.ext.{ns}") for p in _resolve_joy_paths()]

    import importlib.util as importer
    for mod_path, mod_name in candidates:
        if not os.path.isfile(mod_path): continue
        spec, module = importer.spec_from_file_location(mod_name, mod_path), None
        if spec and spec.loader:
            module = importer.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except (SyntaxError, ImportError, Exception) as e:
                raise JoyModuleError(str(e), filename=mod_path, joy_token=ns, joy_meta=meta) from e
        _LIB_MODULES[ns] = module
        return module
    raise JoyModuleError(f"Module `{ns}` not found.", joy_token=ns, joy_meta=meta)


def iter_module_operators(ns: str, *, meta: dict | None = None):
    """Yield `(joy_name, py_function)` pairs for all operators in a module for bulk loading."""
    py_module = load_library_module(ns, meta=meta)
    # Require explicit operator registry on module; otherwise treat as module error.
    if not hasattr(py_module, '__operators__') or not isinstance(getattr(py_module, '__operators__'), list):
        raise JoyModuleError(f"Module `{ns}` is missing operator registry `__operators__`.", joy_token=f"{ns}", joy_meta=meta)
    # All modules require an explicit registry of operators defined.
    for w in getattr(py_module, '__operators__', []):
        if not (py_name := getattr(w, '__name__', '')): continue
        yield get_joy_name(py_name), w


def _normalize_expected_type(tp):
    if tp is Any: return Any
    if isinstance(tp, TypeVar):
        if (bound := tp.__bound__):
            return _normalize_expected_type(bound)
        raise JoyTypeError("TypeVar was empty, treating as invalid type {tp}.")
    if isinstance(tp, (type, tuple, UnionType)): return tp

    if (origin := get_origin(tp)) is not None:
        if origin in (list, tuple, dict, set, frozenset): return origin
        if isinstance(origin, type): return origin
        raise JoyTypeError(f"Unknown generic in type definition for {tp}.")

    if isinstance(tp, (ForwardRef, str)):
        raise JoyTypeError("Forward references and strings-as-types not supported.")
    raise JoyTypeError(f"Unknown type to normalize: {tp} {type(tp)}")


def _is_stack_annotation(annotation: Any) -> bool:
    if isinstance(annotation, ForwardRef) or hasattr(annotation, '__forward_arg__'):
        annotation = annotation.__forward_arg__
    if annotation is Stack:
        return True
    if isinstance(annotation, str):
        return annotation == 'Stack' or annotation.endswith('.Stack')
    return False


def get_stack_effects(*, fn: Callable, name: str = None) -> dict:
    """Parse the type annotations from Python to determine the stack effects in Joy.

    Arity (input) conventions:
        -2: pass entire stack as-is to function
        -1: expand stack into varargs (*stk)
        >=0: pop that many items from the stack

    Valency (output) conventions:
        -1: replace stack with retval
        0: no changes to stack
        1: single output expected
        >=1: tuple of multiple outputs expected
    """
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

    # Special cases when stack be passed in directly and restored directly.
    pass_stack = (len(positional) == 1 and _is_stack_annotation(positional[0].annotation) and not has_varargs)
    replace_stack = (name in {'unstack'}) or allow_variadic_stack  # Allow stack replacement semantics.

    meta = {
        'arity': (-2 if pass_stack else (-1 if (has_varargs and len(positional) == 0) else len(positional))),
        'valency': -1 if replace_stack else (0 if returns_none else (len(outputs) if returns_tuple else 1)),
        'inputs': [] if pass_stack else list(reversed([_normalize_expected_type(p.annotation) for p in positional])),
        'outputs': list(reversed(outputs)),
    }
    return meta
