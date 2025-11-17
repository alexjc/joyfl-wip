## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

from typing import Any, Callable
from collections import deque

from .types import Operation, Stack, nil
from .errors import JoyModuleError
from .parser import parse
from .linker import link_body, load_joy_library
from .library import Library
from .builtins import load_builtins_library
from .formatting import list_to_stack as _list_to_stack, stack_to_list as _stack_to_list
from .interpreter import interpret, can_execute, interpret_step
from .loader import iter_joy_module_candidates, iter_module_operators


class Runtime:
    """Minimal runtime facade focused on embedding and extension."""

    def __init__(self, library: Library | None = None):
        self.library = library or load_builtins_library()

        self.library.joy_module_loader = self._joy_loader
        self.library.py_module_loader = self._py_loader

    def _joy_loader(self, lib: Library, ns: str, meta: dict | None) -> None:
        context_lib: Library = lib
        for src in iter_joy_module_candidates(ns):
            if not src.exists(): continue
            source_text = src.read_text(encoding="utf-8")
            for typ, data in parse(source_text, filename=str(src)):
                if typ == "library":
                    context_lib = self._load_joy_block(lib, data, str(src), context_lib, expected_ns=ns, meta=meta)
            break

    def _py_loader(self, lib: Library, ns: str, op: str, meta: dict | None) -> None:
        for joy_name, py_fn in iter_module_operators(ns, meta=meta):
            lib.add_function(f"{ns}.{joy_name}", py_fn)
        lib.mark_module_loaded(ns)


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

    def _load_joy_block(self, export_lib: Library, data: dict, filename: str,
                        context_lib: Library, *, expected_ns: str | None,
                        meta: dict | None) -> Library:
        if (declared_ns := data.get("module")) != expected_ns and expected_ns is not None:
            raise JoyModuleError(
                f"Module `{declared_ns}` declared in `{filename}` does not match expected prefix `{expected_ns}`.",
                joy_token=expected_ns, filename=filename, joy_meta=meta)
        context = load_joy_library(export_lib, data, filename, context_lib)
        if module_name := (declared_ns or expected_ns):
            export_lib.mark_module_loaded(module_name)
        return context

    def _execute(self, source: str, filename: str | None, verbosity: int,
                 validate: bool, stats: dict | None):
        out = None
        context_lib: Library = self.library
        for typ, data in parse(source, filename=filename):
            if typ == 'term':
                prg, _ = link_body(data, meta={'filename': filename, 'lines': (2**32, -1)}, lib=context_lib)
                out = interpret(prg, lib=self.library, verbosity=verbosity, validate=validate, stats=stats)
            elif typ == 'library':
                context_lib = self._load_joy_block(self.library, data, filename, context_lib, expected_ns=None, meta=None)
                out = nil
        return out

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
