## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import sys
import time
import traceback
from pathlib import Path
from dataclasses import dataclass

import click

from .types import nil
from .errors import JoyError, JoyParseError, JoyNameError, JoyIncompleteParse, JoyAssertionError, JoyImportError
from .parser import format_parse_error_context, print_source_lines, format_source_lines
from .formatting import write_without_ansi, format_item, show_stack

from . import api


@dataclass(frozen=True)
class RuntimeConfig:
    verbose: int
    validate: bool
    ignore: bool
    stats: bool
    plain: bool


@dataclass
class ExecutionItem:
    source: str
    filename: str


class JoyRunner:
    def __init__(self, config: RuntimeConfig):
        self.verbose = config.verbose
        self.validate = config.validate
        self.ignore = config.ignore
        self.stats_enabled = config.stats
        self.plain = config.plain

        if self.plain:
            writer = write_without_ansi(sys.stdout.write)
            sys.stdout.write, sys.stderr.write = writer, writer

        self.runtime = api._RUNTIME
        self.total_stats = {'steps': 0, 'start': time.time()} if self.stats_enabled else None
        self.failure = False
        self.executed_items = 0

        self._load_stdlib()

    def _load_stdlib(self) -> None:
        base = Path(__file__).resolve().parent
        candidates = (d / 'libs' / 'stdlib.joy' for d in (base, *base.parents[:2]))
        stdlib_path = next((p for p in candidates if p.exists()), Path('libs/stdlib.joy'))
        source_text = stdlib_path.read_text(encoding='utf-8')
        self._load_library(source_text, 'libs/stdlib.joy', validate=self.validate)

    def _maybe_fatal_error(self, message: str, detail: str, exc_type: str = None, context: str = '', is_repl: bool = False) -> None:
        header = detail if not exc_type else f"{detail} (Exception: \033[33m{exc_type}\033[0m)"
        print(f'\033[30;43m {message} \033[0m {header}\n{context}', file=sys.stderr)
        if not is_repl and not self.ignore: sys.exit(1)

    def _handle_exception(self, exc, filename: str, source: str, is_repl: bool = False) -> bool:
        if isinstance(exc, JoyParseError):
            if is_repl and isinstance(exc, JoyIncompleteParse): return True
            context = format_parse_error_context(filename, exc.line, exc.column, exc.token, source=source)
            context += f"\n\033[90m{str(exc).replace(chr(10), ' ').replace(chr(9), ' ')}\033[0m\n"
            self._maybe_fatal_error("SYNTAX ERROR.", f"Parsing `\033[97m{filename}\033[0m` caused a problem!", type(exc).__name__, context, is_repl)
        elif isinstance(exc, JoyNameError):
            detail = f"Term `\033[1;97m{exc.joy_token}\033[0m` from `\033[97m{filename}\033[0m` was not found in library!"
            context = '\n' + format_source_lines(exc.joy_meta, exc.joy_token)
            self._maybe_fatal_error("LINKER ERROR.", detail, type(exc).__name__, context, is_repl)
        elif isinstance(exc, JoyAssertionError):
            print(f'\033[30;43m ASSERTION FAILED. \033[0m Function \033[1;97m`{exc.joy_op}`\033[0m raised an error.\n', file=sys.stderr)
            print_source_lines(exc.joy_op, self.runtime.library.quotations, file=sys.stderr)
            print(f'\033[1;33m  Stack content is\033[0;33m\n    ', end='', file=sys.stderr)
            show_stack(exc.joy_stack, width=None, file=sys.stderr, abbreviate=True)
            print('\033[0m', file=sys.stderr)
            if not is_repl and not self.ignore: sys.exit(1)
        elif isinstance(exc, JoyImportError):
            detail = f"Importing library module failed while resolving `{exc.joy_token}`: \033[97m{exc.filename}\033[0m"
            tb_lines = traceback.format_exception(exc.__cause__ if exc.__cause__ else exc, chain=False)
            traceback_text = ''.join([line for line in tb_lines if "src/joyfl/" not in line and "<frozen" not in line]).rstrip() + '\n'
            source_context = format_source_lines(exc.joy_meta, exc.joy_token)
            self._maybe_fatal_error("IMPORT ERROR.", detail, type(exc).__name__, '\n' + '\n'.join((traceback_text, source_context)), is_repl)
        elif isinstance(exc, Exception):
            print(f'\033[30;43m RUNTIME ERROR. \033[0m Function \033[1;97m`{exc.joy_op}`\033[0m caused an error in interpret! (Exception: \033[33m{type(exc).__name__}\033[0m)', file=sys.stderr)
            tb_lines = traceback.format_exc().split('\n')
            print(*[line for line in tb_lines if 'lambda' in line], sep='\n', end='\n', file=sys.stderr)
            print_source_lines(exc.joy_op, self.runtime.library.quotations, file=sys.stderr)
            traceback.print_exc()
            if not is_repl and not self.ignore: sys.exit(1)
        return False

    def _load_library(self, source: str, filename: str, validate: bool | None = None) -> bool:
        try:
            self.runtime.load(source, filename=filename, validate=self.validate if validate is None else validate)
            return True
        except (JoyError, Exception) as exc:
            self._handle_exception(exc, filename, source, is_repl=False)
            return False

    def execute_items(self, items: list[ExecutionItem]) -> None:
        for item in items:
            self._execute_script(item.source, item.filename)

    def _execute_script(self, source: str, filename: str, is_repl: bool = False, print_result: bool = False) -> None:
        try:
            result = self.runtime.run(source, filename=filename, verbosity=self.verbose, validate=self.validate, stats=self.total_stats)
            if result is None and not is_repl:
                self.failure = True
                if not self.ignore: sys.exit(1)
            elif print_result and result is not nil:
                print(format_item(result.head))
        except (JoyError, Exception) as exc:
            self._handle_exception(exc, filename, source, is_repl=is_repl)
        else:
            self.executed_items += 1

    def repl(self) -> None:
        if sys.platform != "win32": import readline

        print('joyfl - Functional stack language REPL; type Ctrl+C to exit.')
        source = ""

        while True:
            try:
                prompt = "\033[36m<<< \033[0m" if not source.strip() else "\033[36m... \033[0m"
                line = input(prompt)
                if len(line.strip()) == 0: continue
                if line.strip() in ('quit', 'exit'): break
                source += line + " "

                try:
                    stack = self.runtime.run(source, filename='<REPL>', verbosity=self.verbose, validate=self.validate)
                    if stack is not nil: print("\033[90m>>>\033[0m", format_item(stack[-1]))
                    source = ""
                except (JoyError, Exception) as exc:
                    if not self._handle_exception(exc, '<REPL>', source, is_repl=True):
                        source = ""

            except (KeyboardInterrupt, EOFError):
                print(""); break

    def finalize(self) -> int:
        if self.total_stats and self.executed_items > 0:
            elapsed_time = time.time() - self.total_stats['start']
            print(f"\n\033[97m\033[48;5;30m STATISTICS. \033[0m")
            print(f"step\t\033[97m{self.total_stats['steps']:,}\033[0m")
            print(f"time\t\033[97m{elapsed_time:.3f}s\033[0m")
        return 1 if self.failure else 0


def _inline_command_source(index: int, command: str) -> ExecutionItem:
    source = command.rstrip()
    if not source.endswith('.'):
        source += ' .'
    return ExecutionItem(source + '\n', f'<INPUT_{index}>')


def _parse_dev_tokens(tokens: list[str]) -> list[tuple[str, Path | str | None]]:
    actions: list[tuple[str, Path | str | None]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == '--':
            index += 1
            continue
        if token in ('-c', '--command'):
            index += 1
            if index >= len(tokens):
                raise click.BadParameter("Missing inline Joy code after -c/--command option.")
            actions.append(('command', tokens[index]))
            index += 1
            continue
        if token.startswith('-c=') or token.startswith('--command='):
            _, value = token.split('=', 1)
            if value == '':
                raise click.BadParameter("Empty Joy code supplied to command option.")
            actions.append(('command', value))
            index += 1
            continue
        if token in ('-r', '--repl'):
            actions.append(('repl', None))
            index += 1
            continue
        if token.startswith('-'):
            raise click.BadParameter(f"Unknown option `{token}`.")
        path = Path(token)
        if not path.exists():
            raise click.BadParameter(f"File `{token}` not found.")
        if path.suffix != '.joy':
            raise click.BadParameter(f"Expected `.joy` source file, got `{token}`.")
        actions.append(('file', path))
        index += 1
    return actions


@click.group(invoke_without_command=True, context_settings={'ignore_unknown_options': True, 'allow_extra_args': True})
@click.option('--verbose', '-v', default=0, count=True, help='Enable verbose interpreter execution.')
@click.option('--validate', is_flag=True, help='Enable type and stack validation before each operation.')
@click.option('--ignore', '-i', is_flag=True, help='Ignore errors and continue executing.')
@click.option('--stats', is_flag=True, help='Display execution statistics (e.g., number of steps).')
@click.option('--plain', '-p', is_flag=True, help='Strip ANSI color codes and redirect stderr to stdout.')
@click.pass_context
def cli(ctx: click.Context, verbose: int, validate: bool, ignore: bool, stats: bool, plain: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj['config'] = RuntimeConfig(verbose=verbose, validate=validate, ignore=ignore, stats=stats, plain=plain)

    if ctx.invoked_subcommand is not None:
        return

    # When invoked via module entry (python -m joyfl), we route in __main__ block.
    return


@cli.command('run-file')
@click.argument('script', type=click.File('r', encoding='utf-8'))
@click.argument('runtime_args', nargs=-1)
@click.pass_context
def run_file(ctx: click.Context, script, runtime_args: tuple[str, ...]) -> None:
    runner = JoyRunner(ctx.obj['config'])
    runner.execute_items((ExecutionItem(script.read(), script.name or '<STDIN>'),))
    ctx.exit(runner.finalize())


@cli.command('run-mod')
@click.argument('name')
@click.pass_context
def run_module(ctx: click.Context, name: str) -> None:
    runner = JoyRunner(ctx.obj['config'])

    if '.' in name:
        module_name, module_term = name.split('.', 1)
        module_term = module_term or 'main'
    else:
        module_name, module_term = name, 'main'

    # Load Joy library module from local libs/ directories if present, then execute <module>.main
    base = Path(__file__).resolve().parent
    for d in (base, *base.parents[:2]):
        src = d / 'libs' / f"{module_name}.joy"
        if not src.exists():
            continue
        existing = set(runner.runtime.library.quotations.keys())
        source_text = src.read_text(encoding='utf-8')
        runner._load_library(source_text, str(src), validate=ctx.obj['config'].validate)
        # Namespace new public quotations for dotted access (module.term)
        for qname in runner.runtime.library.quotations.keys() - existing:
            if '.' in qname:
                continue
            prog, qmeta = runner.runtime.library.quotations[qname]
            runner.runtime.library.quotations.setdefault(f"{module_name}.{qname}", (prog, qmeta))
        break

    program = f"{module_name}.{module_term} .\n"
    runner.execute_items((ExecutionItem(program, f'<MOD:{module_name}.{module_term}>'),))
    ctx.exit(runner.finalize())


@cli.command('run-dev', context_settings={'ignore_unknown_options': True, 'allow_extra_args': True})
@click.argument('tokens', nargs=-1)
@click.pass_context
def run_dev(ctx: click.Context, tokens: tuple[str, ...]) -> None:
    runner = JoyRunner(ctx.obj['config'])
    actions = _parse_dev_tokens(list(tokens))

    command_index = 1
    for action, payload in actions:
        if action == 'file':
            runner.execute_items((ExecutionItem(payload.read_text(encoding='utf-8'), str(payload)),))
        elif action == 'command':
            item = _inline_command_source(command_index, payload)
            runner._execute_script(item.source, item.filename, is_repl=False, print_result=True)
            command_index += 1
        elif action == 'repl':
            runner.repl()
        else:
            raise NotImplementedError

    if not actions:
        runner.repl()
    ctx.exit(runner.finalize())


@cli.command('run-repl')
@click.pass_context
def run_repl(ctx: click.Context) -> None:
    runner = JoyRunner(ctx.obj['config'])
    runner.repl()
    ctx.exit(runner.finalize())


def main(argv: list[str] | None = None) -> None:
    a = list(sys.argv[1:] if argv is None else argv)
    g = [t for t in a if t in ('--validate','--ignore','--stats','--plain','-i','-p') or t.startswith('-v')]
    r = [t for t in a if t not in g]
    pos = [t for t in r if not t.startswith('-')]
    has_dev_opt = any(t in ('-c', '-r', '--repl') or t.startswith('--command') for t in r)

    if len(r) == 0:
        # No args: if stdin has data, treat as file '-', else REPL
        cmd, tail = ('run-file', ['-']) if not sys.stdin.isatty() else ('run-repl', [])
    elif '-m' in r:
        i = r.index('-m')
        if i + 1 >= len(r): raise SystemExit("Expected module name after -m.")
        cmd, tail = 'run-mod', [r[i+1]]
    elif r == ['-'] or (len(r) >= 2 and r[0] == '-f' and r[1] == '-'):
        cmd, tail = 'run-file', ['-']
    elif '--repl' in a:
        cmd, tail = 'run-repl', []
    elif len(pos) == 1:
        tok = pos[0]
        if tok.endswith('.joy') and Path(tok).exists():
            cmd, tail = 'run-file', [tok]
        else:
            if not has_dev_opt and all(part.isidentifier() for part in tok.split('.')):
                cmd, tail = 'run-mod', [tok]
            else:
                cmd, tail = 'run-dev', r
    else:
        cmd, tail = 'run-dev', r

    cli.main(args=[*g, cmd, *tail], prog_name='joyfl')


if __name__ == "__main__":
    main()
