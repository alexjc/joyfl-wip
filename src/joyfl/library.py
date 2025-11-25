## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Callable
from collections import ChainMap
from dataclasses import dataclass, field, replace

from .types import Stack, Quotation, StructMeta, TypeKey
from .errors import JoyNameError
from .loader import get_stack_effects


def is_module_name(x):
    return x[0].isalpha() and all(ch.isalpha() or ch.isdigit() for ch in x[1:])


@dataclass
class Library:
    functions: dict[str, Callable[..., Any]]
    combinators: dict[str, Callable[..., Any]]
    quotations: dict[str, Quotation]
    constants: dict[str, Any]
    factories: dict[str, Callable[[], Any]]
    aliases: dict[str, str] = field(default_factory=dict)
    joy_module_loader: Callable | None = None
    py_module_loader: Callable | None = None
    loaded_modules: set[str] = field(default_factory=set)
    struct_types: dict[TypeKey, StructMeta] = field(default_factory=dict)

    # Registration helpers
    def add_function(self, name: str, fn: Callable[..., Any]) -> None:
        fn, meta = _make_wrapper(fn, name)
        fn.__joy_meta__ = meta
        self.functions[name] = fn

    def add_quotation(self, name: str, program: list, meta: dict) -> None:
        self.quotations[name] = Quotation(program=program, meta=meta, visibility="public", module=None)

    def ensure_consistent(self) -> None:
        for _, fn in list(self.functions.items()):
            assert hasattr(fn, '__joy_meta__')

    def _maybe_load_py_module(self, resolved_name: str, meta: dict | None) -> None:
        if '.' not in resolved_name or self.py_module_loader is None:
            return
        ns, op = resolved_name.split('.', 1)
        if is_module_name(ns) and ns not in self.loaded_modules:
            # Load and register all operators/factories from the Python module at once.
            self.py_module_loader(self, ns, op, meta)

    def get_quotation(self, name: str, *, meta: dict | None = None) -> Quotation | None:
        resolved_name = self.aliases.get(name, name)
        if '.' in resolved_name and self.joy_module_loader is not None:
            if (ns := resolved_name.split('.', 1)[0]) and is_module_name(ns) and ns not in self.loaded_modules:
                self.joy_module_loader(self, ns, meta)
        if (quot := self.quotations.get(resolved_name)) and quot.visibility != "private":
            return quot
        return None

    def get_function(self, name: str, *, meta: dict | None = None) -> Callable[..., Any]:
        resolved_name = self.aliases.get(name, name)
        self._maybe_load_py_module(resolved_name, meta)
        if (function := self.functions.get(resolved_name)) is not None:
            return function
        raise JoyNameError(f"Operation `{name}` not found in library.", joy_token=name, joy_meta=meta)

    def get_factory(self, name: str, *, meta: dict | None = None, joy_token: str, strict: bool = False) -> Callable[[], Any] | None:
        resolved_name = self.aliases.get(name, name)
        self._maybe_load_py_module(resolved_name, meta)
        if (factory := self.factories.get(resolved_name)) is not None:
            return factory
        if strict:
            raise JoyNameError(f"Unknown factory `{joy_token}`.", joy_token=joy_token, joy_meta=meta)
        return None

    def with_overlay(self) -> "Library":
        """Create new view sharing all structure with this one, except for an overlaid `quotations` mapping."""
        overlay_quotations = ChainMap({}, self.quotations)
        return replace(self, quotations=overlay_quotations)

    def mark_module_loaded(self, ns: str):
        self.loaded_modules.add(ns)


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
        case -2: # pass stack as-is
            def w_s(stk: Stack):
                return push(stk, fn(stk))
            return w_s, meta
        case -1: # expand stack
            def w_n(stk: Stack):
                return push(stk, fn(*stk))
            return w_n, meta
        case 0: # no arguments
            def w_0(stk: Stack):
                return push(stk, fn())
            return w_0, meta
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
