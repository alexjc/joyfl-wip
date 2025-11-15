## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import ast
from fractions import Fraction

from .types import Operation, Quotation
from .errors import JoyError, JoyNameError
from .library import Library


def link_body(tokens: list, meta: dict, lib: Library):
    assert meta is not None
    lines = meta.get('lines', (0, 0))
    signature = meta.get('signature')

    stack = tuple()
    output = []
    meta = {'filename': meta.get('filename'), 'start': lines[0], 'finish': -1}
    if signature is not None:
        meta['signature'] = signature

    for typ, token, mt in tokens:
        token = token.lstrip(':')

        if meta['filename'] == mt['filename'] and 'lines' in mt:
            meta['start'] = min(meta['start'], mt['lines'][0])
            meta['finish'] = max(meta['finish'], mt['lines'][1])
            mt['start'] = mt['lines'][0]; mt['finish'] = mt['lines'][1]; del mt['lines']

        if token == '[':
            stack = (stack, (output, meta))
            output, meta = [], mt
        elif token == ']':
            stack[-1][0].append(output)
            (stack, (output, meta)) = stack
        elif token in lib.combinators:
            output.append(Operation(Operation.COMBINATOR, lib.combinators[token], token, mt))
        elif token in lib.constants:
            output.append(lib.constants[token])
        elif (name := token.lstrip('@')) in lib.factories or token.startswith('@'):
            if not (factory := lib.factories.get(name)):
                raise JoyNameError(f"Unknown factory `{token}`.", joy_op=token, joy_meta=meta)
            output.append(factory())
        elif (q := lib.quotations.get(token)) and q.visibility != "private":
            mt['body'] = q.meta
            if q.meta and 'signature' in q.meta:
                mt['signature'] = q.meta['signature']
            output.append(Operation(Operation.EXECUTE, q.program, token, mt))
        elif token.startswith('"') and token.endswith('"'):
            output.append(ast.literal_eval(token))
        elif token.startswith("'"):
            output.append(bytes(token[1:], encoding='utf-8'))
        elif '⁄' in token[1:-1] and all(ch.isdigit() or ch == '⁄' for ch in token):
            output.append(Fraction(*map(int, token.split('⁄'))))
        elif token.isdigit() or token[0] == '-' and token[1:].isdigit():
            output.append(int(token))
        elif len(token) > 1 and token.count('.') == 1 and token.count('-') <= 1 and token.lstrip('-').replace('.', '').isdigit():
            output.append(float(token))
        elif (fn := lib.get_function(token, meta=mt)):
            output.append(Operation(Operation.FUNCTION, fn, token, mt))
        else:
            raise JoyNameError(f"Unknown instruction `{token}`.", joy_token=token, joy_meta=mt)

    assert len(stack) == 0
    return output, meta


def _populate_joy_definitions(definitions: list, lib: Library, visibility: str, module: str):
    def _fill_recursive_calls(n):
        if isinstance(n, list): return [_fill_recursive_calls(t) for t in n]
        if isinstance(n, Operation) and n.ptr is None: n.ptr = prg
        return n

    for (_, key, mt), tokens in definitions:
        # Placeholder for forward/self-references; `program` is None until the body has been fully linked.
        quot = Quotation(program=None, meta={}, visibility=visibility, module=module)
        lib.quotations[key] = quot
        try:
            prg, meta = link_body(tokens, meta=mt, lib=lib)
            quot.program, quot.meta = _fill_recursive_calls(prg), meta
        except JoyError:
            del lib.quotations[key]
            raise


def load_joy_library(export_lib: Library, sections: dict, filename: str, context_lib: Library) -> Library:
    """Load PRIVATE and PUBLIC definitions, linked against context and exported to another library."""
    private_defs = sections.get("private") or []
    public_defs = sections.get("public") or []
    module_name = sections.get("module")
    # Libraries without a module name specified are considered global.
    export_scope = f"{module_name}." if module_name else ""
    # Overlay for definitions: writes go to the local dict, reads fall back to context.
    local_lib = context_lib.with_overlay()

    # Link PRIVATE first so PUBLIC can depend on them. Mark them first as "local" so they can be found.
    _populate_joy_definitions(private_defs, lib=local_lib, visibility="local", module=module_name)
    _populate_joy_definitions(public_defs, lib=local_lib, visibility="public", module=module_name)

    def _export(defs):
        for (typ, name, _mt), _tokens in defs:
            if name not in local_lib.quotations: continue
            quot = local_lib.quotations[name]
            # All quotations are exported so they can be printed & debugged, but marked "private" if necessary.
            export_lib.quotations[export_scope + name] = Quotation(
                program=quot.program, meta=quot.meta,
                visibility="private" if quot.visibility == "local" else "public",
                module=quot.module,
            )

    # Export MODULE definitions into the global library.
    _export(public_defs)
    _export(private_defs)

    return local_lib
