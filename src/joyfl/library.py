## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from dataclasses import dataclass, field
from typing import Any, Callable

from .types import Stack
from .errors import JoyNameError
from .loader import get_stack_effects


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

    def get_function(self, name: str) -> Callable[..., Any]:
        resolved_name = self.aliases.get(name, name)
        if (fn := self.functions.get(resolved_name)) is None:
            raise JoyNameError(f"Operation `{name}` not found in library.", token=name)
        return fn


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
