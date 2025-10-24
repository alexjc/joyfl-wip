## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from dataclasses import dataclass, field
from typing import Any, Callable

from .types import Stack
from .errors import JoyNameError, JoyImportError
from .loader import get_stack_effects, resolve_module_op


@dataclass
class Library:
    functions: dict[str, Callable[..., Any]]
    combinators: dict[str, Callable[..., Any]]
    quotations: dict[str, tuple[list, dict]]  # name -> (program, meta)
    constants: dict[str, Any]
    factories: dict[str, Callable[[], Any]]
    aliases: dict[str, str] = field(default_factory=dict)

    # Registration helpers
    def add_function(self, name: str, fn: Callable[..., Any]) -> None:
        fn, meta = _make_wrapper(fn, name)
        fn.__joy_meta__ = meta
        self.functions[name] = fn

    def add_quotation(self, name: str, program: list, meta: dict) -> None:
        self.quotations[name] = (program, meta)

    def ensure_consistent(self) -> None:
        for _, fn in list(self.functions.items()):
            assert hasattr(fn, '__joy_meta__')

    def get_function(self, name: str, *, meta: dict | None = None) -> Callable[..., Any]:
        resolved_name = self.aliases.get(name, name)
        if (fn := self.functions.get(resolved_name)) is not None:
            return fn
        if '.' in resolved_name:
            try:
                py_fn = resolve_module_op(*resolved_name.split('.', 1))
            except ImportError as e:
                raise JoyImportError(str(e), joy_op=resolved_name, joy_meta=meta) from e
            except JoyNameError as e:
                raise JoyNameError(e.args[0] if e.args else "Unknown instruction", token=getattr(e, 'token', None) or resolved_name, joy_op=getattr(e, 'joy_op', None) or resolved_name, joy_meta=meta) from e
            fn, meta = _make_wrapper(py_fn, resolved_name)
            fn.__joy_meta__ = meta
            self.functions[resolved_name] = fn
            return fn
        raise JoyNameError(f"Operation `{name}` not found in library.", token=name, joy_op=name, joy_meta=meta)


def _make_wrapper(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    meta = get_stack_effects(fn=fn, name=name)
    
    match meta['valency']:
        case -1:
            def push(_, res): return res
        case 0:
            def push(base, _): return base
        case 1:
            def push(base, res): return Stack(base, res)
        case _:
            def push(base, res):
                for v in res: base = Stack(base, v)
                return base

    match meta['arity']:
        case -1:
            def w_n(stk: Stack):
                return push(stk, fn(*stk))
            return w_n, meta
        case 1:
            def w_1(stk: Stack):
                base, a = stk
                return push(base, fn(a))
            return w_1, meta
        case 2:
            def w_2(stk: Stack):
                (base, b), a = stk
                return push(base, fn(b, a))
            return w_2, meta
        case _:
            def w_x(stk: Stack):
                args, base = (), stk
                for _ in range(meta['arity']):
                    base, h = base
                    args = (h,) + args
                return push(base, fn(*args))
            return w_x, meta
