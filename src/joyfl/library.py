## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Callable
from collections import ChainMap
from dataclasses import dataclass, field, replace

from .types import Stack, Quotation, StructMeta
from .errors import JoyNameError, JoyTypeError
from .loader import get_stack_effects


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
    struct_types: dict[bytes, StructMeta] = field(default_factory=dict)

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

    def get_quotation(self, name: str, *, meta: dict | None = None) -> Quotation | None:
        resolved_name = self.aliases.get(name, name)
        if '.' in resolved_name and self.joy_module_loader is not None:
            if (ns := resolved_name.split('.', 1)[0]) not in self.loaded_modules:
                self.joy_module_loader(self, ns, meta)                
                if (prefix := ns + ".") and any(k.startswith(prefix) for k in self.quotations):
                    self.loaded_modules.add(ns)
        if (q := self.quotations.get(resolved_name)) and q.visibility != "private":
            return q
        return None

    def get_function(self, name: str, *, meta: dict | None = None) -> Callable[..., Any]:
        resolved_name = self.aliases.get(name, name)
        if (fn := self.functions.get(resolved_name)) is not None:
            return fn
        if '.' in resolved_name and self.py_module_loader is not None:
            ns, op = resolved_name.split('.', 1)
            if ns not in self.loaded_modules:
                self.py_module_loader(self, ns, op, meta)
                prefix = ns + "."
                if any(k.startswith(prefix) for k in self.functions):
                    self.loaded_modules.add(ns)
            if (fn := self.functions.get(resolved_name)) is not None:
                return fn
        raise JoyNameError(f"Operation `{name}` not found in library.", joy_token=name, joy_meta=meta)

    # Views / overlays
    def with_overlay(self) -> "Library":
        """Create new view sharing all structure with this one, except for an overlaid `quotations` mapping."""
        overlay_quotations = ChainMap({}, self.quotations)
        return replace(self, quotations=overlay_quotations)


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
