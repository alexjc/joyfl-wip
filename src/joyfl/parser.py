## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import os
import sys
import numbers
import textwrap
from typing import Any

import lark
from .types import Stack
from .errors import JoyParseError, JoyIncompleteParse


GRAMMAR = r"""?start: (library | term DOT)*
library: module_clause? private_clause? public_clause? (END | DOT)+
module_clause: "MODULE" NAME
private_clause: ("PRIVATE" | "HIDDEN") definition_sequence
public_clause: ("PUBLIC" | "DEFINE" | "LIBRA") definition_sequence
// definition_sequence: definition (SEPARATOR definition)* SEPARATOR?
definition_sequence: definition (SEPARATOR definition)* SEPARATOR?
definition: NAME stack_effect? EQUALS term
stack_effect: COLON LPAREN stack_pattern ARROW stack_pattern RPAREN
stack_pattern: stack_item*
stack_item: NAME | LSQB stack_pattern RSQB

?term: (NAME | ELLIPSIS | FLOAT | INTEGER | FRACTION | CHAR | STRING | LBRACE CHAR_OR_INT* RBRACE | LSQB term RSQB)*

// COMMENTS
COMMENT.11: /#[^\r\n]*/
MULTILINE_COMMENT.11: /\(\*.*?\*\)/s

// TOKENS
END.9: "END"
ELLIPSIS.10: /\.\.\./
DOT.9: /\.(?![A-Za-z0-9!+\-=<>_,?.])/
SEPARATOR: ";"
STRING.8: /"(?:[^"\\]|\\.)*"/
FLOAT.8: /-?(?:\d+\.\d+)(?:[eE][+-]?\d+)?/
INTEGER.8: /-?\d+/
FRACTION.8: /-?\d+⁄-?\d+/
CHAR.8: /'(?:[^'\[\]\{\}\;\.$\s]+)/
CHAR_OR_INT: (CHAR | INTEGER)
EQUALS: "=="
COLON: ":"
ARROW: "--"
LPAREN: "("
RPAREN: ")"
LSQB: "["
RSQB: "]"
LBRACE: "{"
RBRACE: "}"
NAME: /[^\s\[\]\\(\){\}\;\.\#](?:[A-Za-z0-9!+\-=<>_,?.]*[A-Za-z0-9!+\-=<>_,?])?/

// WHITESPACE
%import common.WS
%ignore WS
%ignore COMMENT
%ignore MULTILINE_COMMENT
"""


TYPE_NAME_MAP: dict[str, Any] = {
    'int': int, 'integer': int, 'float': float, 'double': float,
    'bool': bool, 'boolean': bool,
    'str': str, 'string': str, 'text': str,
    'number': numbers.Number,
    'list': list, 'array': list, 'quot': list,
    'stack': Stack,
    'any': Any, '': Any,
}


def _stack_effect_to_meta(effect: dict | None) -> dict | None:
    if not effect: return None

    def _convert(items):
        converted = []
        for item in items:
            type_name = item.get('type')
            if type_name is None and item.get('quote') is not None:
                type_name = 'quot'
            converted.append(TYPE_NAME_MAP.get((type_name or '').lower(), Any))
        return list(reversed(converted))

    inputs, outputs = effect.get('inputs', []), effect.get('outputs', [])
    return {
        'inputs': _convert(inputs),
        'outputs': _convert(outputs),
        'arity': len(inputs),
        'valency': len(outputs),
    }


_TYPE_HINTS = {name for name in TYPE_NAME_MAP}


def parse(source: str, start='start', filename=None):
    parser = lark.Lark(GRAMMAR, start=start, parser="lalr", lexer="contextual", propagate_positions=True)

    def _stack_pattern(tree):
        items = []
        for item in tree.children:
            if not isinstance(item, lark.Tree) or not item.children:
                continue
            first = item.children[0]
            if isinstance(first, lark.Token) and first.type == 'NAME':
                name = first.value
                if name.startswith(':'):
                    if items:
                        items[-1]['type'] = name[1:] or None
                    else:
                        items.append({'label': None, 'type': name[1:] or None, 'quote': None, 'raw': name})
                    continue
                entry = {'label': name, 'type': None, 'quote': None, 'raw': name}
                if (lower := name.lower()) in _TYPE_HINTS:
                    entry['type'], entry['label'] = lower, None
                items.append(entry)
                continue
            if len(item.children) == 3 and isinstance(item.children[0], lark.Token) and item.children[0].type == 'LSQB':
                items.append({'label': None, 'type': 'quote', 'quote': _stack_pattern(item.children[1]), 'raw': None})
        return items

    def _stack_effect(tree):
        patterns = [ch for ch in tree.children if isinstance(ch, lark.Tree) and ch.data == 'stack_pattern']
        assert len(patterns) > 0, "Stack effects not found as expected."
        inputs = _stack_pattern(patterns[0])
        outputs = _stack_pattern(patterns[1]) if len(patterns) > 1 else []
        return {'inputs': inputs, 'outputs': outputs}

    def _flatten(node):
        if isinstance(node, lark.Tree):
            if node.data == 'stack_effect': return
            for child in node.children:
                yield from _flatten(child)
        elif node.type not in ('SEPARATOR', 'COLON', 'LPAREN', 'RPAREN', 'ARROW'):
            meta = {'filename': filename, 'lines': (node.line, node.end_line),
                    'columns': (node.column, node.end_column)} if hasattr(node, 'line') else {}
            yield (node.type, node.value, meta)

    def _extract_definition(node):
        if not isinstance(node, lark.Tree) or node.data != 'definition':
            return None

        children = list(node.children)
        idx = 0

        name_token = children[idx]; idx += 1
        signature = None
        if idx < len(children) and isinstance(children[idx], lark.Tree) and children[idx].data == 'stack_effect':
            stack_effect = _stack_effect(children[idx])
            signature = _stack_effect_to_meta(stack_effect)
            idx += 1
        if idx < len(children) and isinstance(children[idx], lark.Token) and children[idx].type == 'EQUALS':
            idx += 1

        term_node = children[idx] if idx < len(children) else None
        head = next(_flatten(name_token))
        body = list(_flatten(term_node)) if term_node is not None else []
        if signature is not None:
            meta = dict(head[2]) if head[2] else {}
            meta['signature'] = signature
            head = (head[0], head[1], meta)
        return head, body

    def _traverse(it):
        if isinstance(it, lark.Token):
            if it.type not in ('DOT', 'END'):
                yield 'term', [next(_flatten(it))]
            return
        assert isinstance(it, lark.Tree)

        if it.data == 'library':
            sections = {"module": None, "private": [], "public": []}
            for ch in [c for c in it.children[:-1] if c not in ('END', '.')]:
                key = ch.data.split('_', maxsplit=1)[0]
                if key != 'module':
                    sections[key] = [parsed for definition_node in ch.children[0].children if (parsed := _extract_definition(definition_node))]
            yield 'library', sections
        elif it.data == 'term':
            yield 'term', list(_flatten(it))
        else:
            for ch in it.children:
                yield from _traverse(ch)

    try:
        tree = parser.parse(source)
    except lark.exceptions.ParseError as exc:
        def attr(k): return getattr(exc, k, None)
        token_val = getattr(attr('token'), 'value', None)
        error_class = JoyIncompleteParse if token_val == '' else JoyParseError
        raise error_class(str(exc), filename=filename, line=attr('line'), column=attr('column'), token=token_val) from None
    yield from _traverse(tree)

def load_source_lines(meta, keyword, line):
    if meta['filename'] is None or not os.path.isfile(meta['filename']): return ""
    source = open(meta['filename'], 'r').read()
    lines = [l for l in source.split('\n')[meta['start']-1:meta['finish']]]
    j = line - meta['start']
    lines[j] = lines[j].replace(keyword, f"\033[48;5;30m\033[1;97m{keyword}\033[0m")
    return '\n'.join(lines)

def print_source_lines(op, lib, file=sys.stderr):
    def _contained_in(k, prg):
        if isinstance(prg, list): return any(_contained_in(k, p) for p in prg)
        return id(op) == id(prg)

    src = [(meta, k) for k, (prog, meta) in lib.items() if _contained_in(k, prog)]
    for meta, ctx in src + [(op.meta, op.name)]:
        print(format_source_lines(meta, ctx), end='\n', file=file)
        break

def format_source_lines(meta: dict, identifier: str) -> str:
    header = f"\033[97m  File \"{meta['filename']}\", lines {meta['start']}-{meta['finish']}, in {identifier}\033[0m\n"
    lines = load_source_lines(meta, keyword=identifier, line=meta['start'])
    return header + (textwrap.indent(textwrap.dedent(lines), prefix='    ') + "\n" if lines else "")


def format_parse_error_context(filename, line, column, token_value, source=None):
    lines = source.splitlines(keepends=True) if source else open(filename, 'r').readlines()
    start_line, end_line = max(0, line - 3), min(len(lines), line + 2)
    result = [f"\033[97m  File \"{filename}\", line {line}\033[0m"]

    for i in range(start_line, end_line):
        line_content = lines[i].rstrip('\n')
        line_color = '\033[90m'
        if i+1 == line:
            line_color = '\033[97m'
            if column > 0 and column <= len(line_content):
                line_content = (
                    line_content[:column-1] + 
                    f"\033[48;5;30m\033[1;97m{line_content[column-1:column+len(token_value)-1]}\033[0m" +
                    line_content[column+len(token_value)-1:]
                )
        result.append(f"{line_color}{i+1:>5} |\033[0m {line_content}")
    return '\n' + '\n'.join(result) + '\n'
