## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Callable
from collections import deque

from .types import Operation, Stack, nil
from .parser import parse
from .linker import link_body
from .library import Library
from .builtins import load_builtins_library
from .formatting import list_to_stack as _list_to_stack, stack_to_list as _stack_to_list
from .interpreter import interpret, can_execute, interpret_step


class Runtime:
    """Minimal runtime facade focused on embedding and extension."""

    def __init__(self, library: Library | None = None):
        self.library = library or load_builtins_library()

    # Assembly ────────────────────────────────────────────────────────────────────────────────
    def operation(self, name: str) -> Operation:
        fn = self.library.get_function(name)
        return Operation(Operation.FUNCTION, fn, name, {})

    def quotation(self, *items) -> list:
        return list(items)

    def is_operation(self, x: Any) -> bool:
        return isinstance(x, Operation)

    def is_quotation(self, x: Any) -> bool:
        return isinstance(x, list)

    # Execution ───────────────────────────────────────────────────────────────────────────────
    def run(self, program: str, stack: Stack | None = None, filename: str | None = None,
            verbosity: int = 0, validate: bool = False, stats: dict | None = None) -> Stack:
        return self._execute(program, filename, verbosity, validate, stats)

    def can_step(self, op: Operation, stack: Stack) -> tuple[bool, str]:
        return can_execute(op, stack)

    def do_step(self, queue, stack):
        return interpret_step(deque(queue), stack, self.library)

    def apply(self, op_or_name: Operation | str, stack: Stack) -> Stack:
        op = op_or_name if isinstance(op_or_name, Operation) else self.operation(op_or_name)
        stack, _ = self.do_step([op], stack)
        return stack

    # Loading ─────────────────────────────────────────────────────────────────────────────────
    def load(self, source: str, filename: str | None = None, validate: bool = False) -> None:
        self._execute(source, filename, 0, validate, None)

    def _execute(self, source: str, filename: str | None, verbosity: int,
                 validate: bool, stats: dict | None):
        out = None
        for typ, data in parse(source, filename=filename):
            if typ == 'term':
                prg, _ = link_body(data, meta={'filename': filename, 'lines': (2**32, -1)}, lib=self.library)
                out = interpret(prg, lib=self.library, verbosity=verbosity, validate=validate, stats=stats)
            elif typ == 'library':
                self._populate_definitions(data['public'])
                out = nil
        return out

    def _populate_definitions(self, public_defs: list):
        def _fill_recursive_calls(n):
            if isinstance(n, list): return [_fill_recursive_calls(t) for t in n]
            if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
            return n

        for (_, key, mt), tokens in public_defs:
            self.library.quotations[key] = (None, {})  # placeholder for forward/self references
            try:
                prg, meta = link_body(tokens, meta=mt, lib=self.library)
                self.library.quotations[key] = (_fill_recursive_calls(prg), meta)
            except:
                del self.library.quotations[key]
                raise

    # Registration ────────────────────────────────────────────────────────────────────────────
    def register_operation(self, name: str, func: Callable) -> None:
        self.library.add_function(name, func)

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        self.library.factories[name] = factory

    # Introspection ───────────────────────────────────────────────────────────────────────────
    def get_signature(self, name: str) -> dict:
        fn = self.library.get_function(name)
        return fn.__joy_meta__

    def list_operations(self) -> dict[str, dict]:
        return {n: self.library.get_function(n).__joy_meta__ for n in self.library.functions.keys()}

    def to_stack(self, values: list) -> Stack:
        return _list_to_stack(values)

    def from_stack(self, stack: Stack) -> list:
        return _stack_to_list(stack)
