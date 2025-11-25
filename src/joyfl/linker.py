## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import ast
from fractions import Fraction

from .types import Operation, Quotation, StructMeta, TypeKey
from .errors import JoyError, JoyNameError, JoyTypeDuplicate, JoyUnknownStruct
from .library import Library


def _resolve_struct_types_in_signature(signature: dict, lib: Library, meta: dict) -> None:
    """Replace struct TYPE_NAME strings in stack-effect metadata with runtime struct types."""
    def _resolve(seq):
        if seq is None: return

        for t in seq:
            if not isinstance(t, TypeKey):
                yield t
            elif t not in lib.struct_types:
                raise JoyUnknownStruct(f"Unknown struct type `{t.to_str()}` in stack effect.", joy_token=t.to_str(), joy_meta=meta)
            else:
                yield lib.struct_types[t]

    signature["inputs"] = list(_resolve(signature["inputs"]))
    signature["outputs"] = list(_resolve(signature["outputs"]))

    # Symbolic stack entries keep their labels/vars; only attach quotation type metadata.
    def _attach(entries):
        for entry in entries:
            if entry.get("kind") == "quotation":
                ref_name = entry.get("type")
                if ref_name and (qt := lib.quotations.get(ref_name)) and qt.type:
                    entry["quote_effect"] = qt.type
            yield entry

    signature["inputs_sym"] = list(_attach(signature.get("inputs_sym", [])))
    signature["outputs_sym"] = list(_attach(signature.get("outputs_sym", [])))


def link_body(tokens: list, meta: dict, lib: Library):
    assert meta is not None
    lines = meta.get('lines', (0, 0))
    signature = meta.get('signature')

    stack = tuple()
    output = []
    meta = {'filename': meta.get('filename'), 'start': lines[0], 'finish': -1}
    if signature is not None:
        _resolve_struct_types_in_signature(signature, lib, meta)
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
        elif (factory := lib.get_factory((name := token.lstrip('@')), meta=mt, joy_token=token, strict=token.startswith('@'))):
            output.append(factory())
        elif (q := lib.get_quotation(token, meta=mt)) is not None:
            mt['body'] = q.meta
            if q.meta and 'signature' in q.meta:
                mt['signature'] = q.meta['signature']
            output.append(Operation(Operation.EXECUTE, q.program, token, mt))
        elif token.startswith('"') and token.endswith('"'):
            output.append(ast.literal_eval(token))
        elif token.startswith("'"):
            output.append(bytes(token[1:], encoding='utf-8'))
        elif '⁄' in token[1:-1] and all(ch.isdigit() or ch == '⁄' for ch in token.lstrip('-')):
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
        if isinstance(n, Operation) and n.ptr is None:
            if (q := lib.quotations.get(n.name)) is not None:
                assert q.program is not None
                n.ptr = q.program
        return n

    # First pass: register placeholders forward-references and mutual-recursion can be resolved later.
    for (_, key, _mt), _tokens in definitions:
        assert key not in lib.quotations
        lib.quotations[key] = Quotation(program=None, meta={}, visibility=visibility, module=module)

    # Second pass: link each body now that all quotation names are known.
    for (_, key, mt), tokens in definitions:
        try:
            prg, meta = link_body(tokens, meta=mt, lib=lib)
        except JoyError:
            for (_, key, _mt), _tokens in definitions:
                lib.quotations.pop(key, None)
            raise

        quot = lib.quotations[key]
        quot.program, quot.meta = prg, meta

    # Third pass: resolve the placeholders that were previously put in place.
    for (_, key, _), _ in definitions:
        quot = lib.quotations.get(key)
        quot.program = _fill_recursive_calls(quot.program)


def load_joy_library(export_lib: Library, sections: dict, filename: str, context_lib: Library) -> Library:
    """Load PRIVATE and PUBLIC definitions, linked against context and exported to another library."""
    private_defs = sections.get("private") or []
    public_defs = sections.get("public") or []
    module_name = sections.get("module")
    # Libraries without a module name specified are considered global.
    export_scope = f"{module_name}." if module_name else ""
    # Overlay for definitions: writes go to the local dict, reads fall back to context.
    local_lib = context_lib.with_overlay()

    def _store_target(target_lib: Library, effect):
        placeholder = Quotation(
            program=None, meta={'type_name': typename, 'filename': filename},
            visibility="public", module=module_name, type=effect
        )
        target_lib.quotations[typename] = placeholder

    # Register TYPEDEFs (structs and quotation types) in the export library.
    for _visibility, typename, type_meta in sections.get("types") or []:
        match type_meta.get("kind"):
            case "product":
                struct_type = StructMeta.from_typedef(typename, tuple(type_meta["fields"]))
                type_key = struct_type.name
                if (existing := export_lib.struct_types.get(type_key)) is not None and existing is not struct_type:
                    raise JoyTypeDuplicate(
                        f"Struct type `{typename}` already registered, and shapes differ.",
                        joy_token=typename, joy_meta={"filename": filename})
                export_lib.struct_types[type_key] = struct_type
            case "quotation":
                effect = type_meta["effect"]
                existing = export_lib.quotations.get(typename)
                if existing is not None and existing.type is not None and existing.type != effect:
                    raise JoyTypeDuplicate(
                        f"Quotation type `{typename}` already registered, and stack effects differ.",
                        joy_token=typename, joy_meta={"filename": filename}
                    )
                _store_target(export_lib, effect)
                _store_target(local_lib, effect)
            case _:
                raise NotImplementedError

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
