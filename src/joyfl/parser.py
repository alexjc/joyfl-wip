## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import os
import sys
import textwrap

import lark


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

?term: (NAME | FLOAT | INTEGER | FRACTION | CHAR | STRING | LBRACE CHAR_OR_INT* RBRACE | LSQB term RSQB)*

// COMMENTS
COMMENT.11: /#[^\r\n]*/
MULTILINE_COMMENT.11: /\(\*.*?\*\)/s

// TOKENS
END.9: "END"
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


def parse(source: str, start='start', filename=None):
    parser = lark.Lark(GRAMMAR, start=start, parser="lalr", lexer="contextual", propagate_positions=True)

    def _flatten(node):
        if isinstance(node, lark.Tree):
            if node.data == 'stack_effect': return  # documentation only for now
            for child in node.children:
                yield from _flatten(child)
        elif node.type not in ('SEPARATOR', 'COLON', 'LPAREN', 'RPAREN', 'ARROW'):
            meta = {'filename': filename, 'lines': (node.line, node.end_line),
                    'columns': (node.column, node.end_column)} if hasattr(node, 'line') else {}
            yield (node.type, node.value, meta)

    def _traverse(it):
        if isinstance(it, lark.Token):
            if it.type not in ('DOT', 'END'):
                yield 'term', [(it.type, it.value, {'filename': filename})]
            return
        assert isinstance(it, lark.Tree)

        if it.data == 'library':
            sections = {"module": None, "private": [], "public": []}
            for ch in [c for c in it.children[:-1] if c not in ('END', '.')]:
                key = ch.data.split('_', maxsplit=1)[0]
                if key != 'module':
                    sections[key] = [(toks[0], toks[2:]) for i in ch.children[0].children if (toks := list(_flatten(i)))]
            yield 'library', sections
        elif it.data == 'term':
            yield 'term', list(_flatten(it))
        else:
            for ch in it.children:
                yield from _traverse(ch)

    tree = parser.parse(source)
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
    for meta, ctx in src + [(op.meta, '')]:
        print(f"\033[97m  File \"{meta['filename']}\", lines {meta['start']}-{meta['finish']}, in {ctx}\033[0m", file=file)
        if (lines := load_source_lines(meta, keyword=op.name, line=op.meta['start'])):
            print(textwrap.indent(textwrap.dedent(lines), prefix='    '), sep='\n', end='\n\n', file=file)
        break

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
