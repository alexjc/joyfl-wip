## joyfl — CLI error integration tests

import os, sys
import subprocess
from pathlib import Path


def run_cli(*cli_args: str | Path, env: dict | None = None, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "joyfl", "--plain"]
    if extra_args:
        args.extend(extra_args)
    args.extend(str(arg) for arg in cli_args)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(args, capture_output=True, text=True, env=merged_env)


def run_cli_input(stdin: str, *cli_args: str | Path, env: dict | None = None, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "joyfl", "--plain"]
    if extra_args:
        args.extend(extra_args)
    args.extend(str(arg) for arg in cli_args)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(args, input=stdin, capture_output=True, text=True, env=merged_env)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_cli_linker_error_shows_context_and_source():
    file_path = repo_root() / "tests" / "error-linker.joy"
    result = run_cli(file_path)
    assert result.returncode != 0
    out = result.stdout
    assert "LINKER ERROR." in out
    assert "File \"" in out  # white header with file path
    assert "lines " in out and ", in " in out  # header fields present
    assert "lines ?-?" not in out


def test_cli_runtime_error_shows_context_and_stack():
    file_path = repo_root() / "tests" / "error-runtime.joy"
    result = run_cli(file_path)
    assert result.returncode != 0
    out = result.stdout
    assert "ASSERTION FAILED." in out
    assert "File \"" in out
    assert "Stack content is" in out
    assert "lines ?-?" not in out


def test_cli_parser_error_shows_context():
    file_path = repo_root() / "tests" / "error-parser.joy"
    result = run_cli(file_path)
    assert result.returncode != 0
    out = result.stdout
    assert "SYNTAX ERROR." in out
    assert "Parsing `" in out
    assert "File \"" in out
    assert "lines ?-?" not in out


def test_cli_import_error_shows_context_and_source():
    root = repo_root()
    file_path = root / "tests" / "error-import.joy"
    env = {"JOY_PATH": str(root / "tests")}
    result = run_cli(file_path, env=env)
    assert result.returncode != 0
    out = result.stdout
    assert "IMPORT ERROR." in out
    assert "File \"" in out
    assert "while resolving `errmod`" in out
    assert "errmod.nop ." in out
    assert "lines ?-?" not in out


def test_cli_import_module_not_found():
    root = repo_root()
    file_path = root / "tests" / "error-import.joy"
    env = {"JOY_PATH": str(root / "tests" / "does-not-exist")}
    result = run_cli(file_path, env=env)
    assert result.returncode != 0
    out = result.stdout
    assert "IMPORT ERROR." in out
    assert "while resolving `errmod`" in out
    assert "File \"" in out
    assert "Traceback (most recent call last):" in out


def test_cli_import_module_exception_shows_traceback():
    root = repo_root()
    file_path = root / "tests" / "error-import.joy"
    env = {"JOY_PATH": str(root / "tests")}
    result = run_cli(file_path, env=env)
    assert result.returncode != 0
    out = result.stdout
    assert "IMPORT ERROR." in out
    assert "Traceback (most recent call last):" in out
    assert "Simulated import failure in tests/errmod.py" in out
    assert "Module `errmod` not found." not in out
    assert "The above exception was the direct cause of the following exception:" not in out
    assert "src/joyfl/" not in out


def _strip_output_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.strip()]


def test_cli_run_file_subcommand_executes_program(tmp_path: Path):
    program = tmp_path / "hello.joy"
    program.write_text('"RUNFILE" put! .\n', encoding='utf-8')

    result = run_cli(program)

    assert result.returncode == 0
    assert _strip_output_lines(result.stdout) == ["RUNFILE"]


def test_cli_dev_mode_executes_mixed_inputs(tmp_path: Path):
    first = tmp_path / "first.joy"
    first.write_text('"FIRST" put! .\n', encoding='utf-8')
    second = tmp_path / "second.joy"
    second.write_text('"THIRD" put! .\n', encoding='utf-8')

    result = run_cli(first, "-c", '"SECOND" put!', second)

    assert result.returncode == 0
    assert _strip_output_lines(result.stdout) == ["FIRST", "SECOND", "THIRD"]

#
# Note: module loading for Joy source via JOY_PATH is currently handled only
#       by explicit CLI path as needed; no extra tests here to enforce semantics.


def test_cli_stdin_implicit_runs_program():
    result = run_cli_input('"IMPLICIT" put! .\n')
    assert result.returncode == 0
    assert _strip_output_lines(result.stdout) == ["IMPLICIT"]


def test_cli_stdin_dash_runs_program():
    result = run_cli_input('"DASH" put! .\n', "-")
    assert result.returncode == 0
    assert _strip_output_lines(result.stdout) == ["DASH"]


def test_cli_validate_stack_error_sets_retcode_and_shows_error(tmp_path: Path):
    program = tmp_path / "type-error.joy"
    program.write_text("i .\n", encoding="utf-8")
    result = run_cli(program, extra_args=["--validate"])

    assert result.returncode != 0
    out = result.stdout
    assert "VALIDATION ERROR." in out
    assert "needs at least 1 item on the stack" in out


def test_cli_run_mod_uses_local_library_helpers(tmp_path: Path):
    # Create a self-contained Joy module in a temporary directory and expose
    # it via JOY_PATH. The module's PUBLIC `main` depends on a PRIVATE/helper
    # word defined in the same file, without requiring any scoped prefix.
    module_source = """MODULE mymod PRIVATE helper == 41 ; PUBLIC main == helper 1 + put! ; END.\n"""

    mod_dir = tmp_path
    mod_path = mod_dir / "mymod.joy"
    mod_path.write_text(module_source, encoding="utf-8")

    env = {"JOY_PATH": str(mod_dir)}
    result = run_cli("-m", "mymod", env=env)

    assert result.returncode == 0
    # `helper 1 + put!` must have executed successfully, printing `42`.
    lines = _strip_output_lines(result.stdout)
    assert "42" in lines[-1]
