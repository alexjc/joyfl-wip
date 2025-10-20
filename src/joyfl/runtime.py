## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Callable

from .types import Operation
from .parser import parse
from .linker import link_body, FUNC, FUNCTIONS, FACTORIES, _make_wrapper
from .interpreter import interpret, can_execute as _can_execute, interpret_step as _interpret_step
from .loader import get_stack_effects, _FUNCTION_SIGNATURES
from .formatting import list_to_stack as _list_to_stack, stack_to_list as _stack_to_list


class Runtime:
    """Minimal runtime facade focused on embedding and extension.

    Notes:
    - For now, this uses the module-level registries in linker (`FUNCTIONS`, `FACTORIES`, `_FUNCTION_SIGNATURES`).
      Registry isolation can be added later without changing the public API.
    """

    def __init__(self):
        self._functions = FUNCTIONS
        self._factories = FACTORIES
        self._signatures = _FUNCTION_SIGNATURES

    # Assembly ────────────────────────────────────────────────────────────────────────────────
    def operation(self, name: str) -> Operation:
        return FUNC(name)

    def quotation(self, *items) -> list:
        return list(items)

    def is_operation(self, x: Any) -> bool:
        return isinstance(x, Operation)

    def is_quotation(self, x: Any) -> bool:
        return isinstance(x, list)

    # Execution ───────────────────────────────────────────────────────────────────────────────
    def run(self, program: str, stack: tuple | None = None, filename: str | None = None,
            verbosity: int = 0, validate: bool = False, stats: dict | None = None,
            library: dict | None = None) -> tuple:
        _, out = self._execute(program, filename, verbosity, validate, stats, library)
        return out

    def can_step(self, op: Operation, stack: tuple) -> tuple[bool, str]:
        return _can_execute(op, stack)

    def do_step(self, queue, stack):
        return _interpret_step(queue, stack)

    # Loading ─────────────────────────────────────────────────────────────────────────────────
    def load(self, source: str, filename: str | None = None, validate: bool = False,
             library: dict | None = None) -> dict:
        env, _ = self._execute(source, filename, 0, validate, None, library)
        return env

    def _execute(self, source: str, filename: str | None, verbosity: int,
                 validate: bool, stats: dict | None, library: dict | None):
        env = library or {}
        out = None
        for typ, data in parse(source, filename=filename):
            if typ == 'term':
                prg, _ = link_body(data, library=env, meta={'filename': filename, 'lines': (2**32, -1)})
                out = interpret(prg, library=env, verbosity=verbosity, validate=validate, stats=stats)
            elif typ == 'library':
                self._populate_definitions(env, data['public'])
                out = tuple()
        return env, out

    def _populate_definitions(self, env: dict, public_defs: list):
        def _fill_recursive_calls(n):
            if isinstance(n, list): return [_fill_recursive_calls(t) for t in n]
            if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
            return n

        for (_, key, mt), tokens in public_defs:
            env[key] = None
            try:
                prg, meta = link_body(tokens, library=env, meta=mt)
                env[key] = (_fill_recursive_calls(prg), meta)
            except:
                del env[key]; raise

    # Registration ────────────────────────────────────────────────────────────────────────────
    def register_operation(self, name: str, func: Callable) -> None:
        self._functions[name] = _make_wrapper(func, name)

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        self._factories[name] = factory

    # Introspection ───────────────────────────────────────────────────────────────────────────
    def get_signature(self, name: str) -> dict:
        return get_stack_effects(name=name)

    def list_operations(self) -> dict[str, dict]:
        return dict(self._signatures)

    def to_stack(self, values: list) -> tuple:
        return _list_to_stack(values)

    def from_stack(self, stack: tuple) -> list:
        return _stack_to_list(stack)
