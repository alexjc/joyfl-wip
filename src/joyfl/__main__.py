## Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘
#
# joyfl — A minimal but elegant dialect of Joy, functional / concatenative stack language.
#

import sys
import time
import traceback
from pathlib import Path

import click

from .types import nil
from .errors import JoyError, JoyParseError, JoyNameError, JoyIncompleteParse, JoyAssertionError, JoyImportError
from .parser import format_parse_error_context, print_source_lines, format_source_lines
from .formatting import write_without_ansi, format_item, show_stack

from . import api as J


@click.command()
@click.argument('files', nargs=-1, type=click.File('r'))
@click.option('--command', '-c', 'commands', multiple=True, type=str, help='Execute Joy code from command line.')
@click.option('--repl', is_flag=True, help='Start REPL after executing commands and files.')
@click.option('--verbose', '-v', default=0, count=True, help='Enable verbose interpreter execution.')
@click.option('--validate', is_flag=True, help='Enable type and stack validation before each operation.')
@click.option('--ignore', '-i', is_flag=True, help='Ignore errors and continue executing.')
@click.option('--stats', is_flag=True, help='Display execution statistics (e.g., number of steps).')
@click.option('--plain', '-p', is_flag=True, help='Strip ANSI color codes and redirect stderr to stdout.')
def main(files: tuple, commands: tuple, repl: bool, verbose: int, validate: bool, ignore: bool, stats: bool, plain: bool):

    if plain is True:
        writer = write_without_ansi(sys.stdout.write)
        sys.stdout.write, sys.stderr.write = writer, writer
    failure = False

    def _maybe_fatal_error(message: str, detail: str, exc_type: str = None, context: str = '', is_repl=False):
        header = detail if not exc_type else f"{detail} (Exception: \033[33m{exc_type}\033[0m)"
        print(f'\033[30;43m {message} \033[0m {header}\n{context}', file=sys.stderr)
        if not is_repl and not ignore: sys.exit(1)

    def _handle_exception(exc, filename, source, is_repl=False):
        if isinstance(exc, JoyParseError):
            if is_repl and isinstance(exc, JoyIncompleteParse): return True
            context = format_parse_error_context(filename, exc.line, exc.column, exc.token, source=source)
            context += f"\n\033[90m{str(exc).replace(chr(10), ' ').replace(chr(9), ' ')}\033[0m\n"
            _maybe_fatal_error("SYNTAX ERROR.", f"Parsing `\033[97m{filename}\033[0m` caused a problem!", type(exc).__name__, context, is_repl)
        elif isinstance(exc, JoyNameError):
            detail = f"Term `\033[1;97m{exc.joy_op}\033[0m` from `\033[97m{filename}\033[0m` was not found in library!"
            context = '\n' + format_source_lines(exc.joy_meta, exc.joy_op)
            _maybe_fatal_error("LINKER ERROR.", detail, type(exc).__name__, context, is_repl)
        elif isinstance(exc, JoyAssertionError):
            print(f'\033[30;43m ASSERTION FAILED. \033[0m Function \033[1;97m`{exc.joy_op}`\033[0m raised an error.\n', file=sys.stderr)
            print_source_lines(exc.joy_op, J.library.quotations, file=sys.stderr)
            print(f'\033[1;33m  Stack content is\033[0;33m\n    ', end='', file=sys.stderr)
            show_stack(exc.joy_stack, width=None, file=sys.stderr); print('\033[0m', file=sys.stderr)
            if not is_repl and not ignore: sys.exit(1)
        elif isinstance(exc, JoyImportError):
            detail = f"Importing library module failed while resolving `{exc.joy_op}`: \033[97m{exc.filename}\033[0m"
            context = '\n' + format_source_lines(exc.joy_meta, exc.joy_op)
            _maybe_fatal_error("IMPORT ERROR.", detail, type(exc).__name__, context, is_repl)
        elif isinstance(exc, Exception):
            print(f'\033[30;43m RUNTIME ERROR. \033[0m Function \033[1;97m`{exc.joy_op}`\033[0m caused an error in interpret! (Exception: \033[33m{type(exc).__name__}\033[0m)\n', file=sys.stderr)
            tb_lines = traceback.format_exc().split('\n')
            print(*[line for line in tb_lines if 'lambda' in line], sep='\n', end='\n', file=sys.stderr)
            print_source_lines(exc.joy_op, J.library.quotations, file=sys.stderr)
            traceback.print_exc()
            if not is_repl and not ignore: sys.exit(1)
        return False

    stdlib_path = Path(__file__).resolve().parent.parent / 'libs' / 'stdlib.joy'
    if not stdlib_path.exists():
        stdlib_path = Path('libs/stdlib.joy')
    J.load(stdlib_path.read_text(encoding='utf-8'), filename='libs/stdlib.joy', validate=validate)

    # Build execution list: files first, then commands.
    items = [(f.read(), f.name) for f in files]
    items += [(cmd, f'<INPUT_{i+1}>') for i, cmd in enumerate(commands)]

    total_stats = {'steps': 0, 'start': time.time()} if stats else None
    for source, filename in items:
        try:
            r = J.run(source, filename=filename, verbosity=verbose, validate=validate, stats=total_stats)
            (r is None and ((failure := True) or (not ignore and sys.exit(1))))
        except (JoyError, Exception) as exc:
            _handle_exception(exc, filename, source, is_repl=False)

    if total_stats and len(items) > 0:
        elapsed_time = time.time() - total_stats['start']
        print(f"\n\033[97m\033[48;5;30m STATISTICS. \033[0m")
        print(f"step\t\033[97m{total_stats['steps']:,}\033[0m")
        print(f"time\t\033[97m{elapsed_time:.3f}s\033[0m")

    # Start REPL if no items were provided or --repl flag was set
    if len(items) == 0 or repl:
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
                    stack = J.run(source, filename='<REPL>', verbosity=verbose, validate=validate)
                    if stack is not nil: print("\033[90m>>>\033[0m", format_item(stack[-1]))
                    source = ""
                except (JoyError, Exception) as exc:
                    if not _handle_exception(exc, '<REPL>', source, is_repl=True):
                        source = ""

            except (KeyboardInterrupt, EOFError):
                print(""); break

    sys.exit(failure)


if __name__ == "__main__":
    main()
