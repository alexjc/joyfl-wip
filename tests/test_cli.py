## joyfl — CLI error integration tests

import os, sys
import subprocess
from pathlib import Path


def run_cli(file_path: Path, *, env: dict | None = None, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "joyfl", "--plain"]
    if extra_args:
        args.extend(extra_args)
    args.append(str(file_path))
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(args, capture_output=True, text=True, env=merged_env)


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
