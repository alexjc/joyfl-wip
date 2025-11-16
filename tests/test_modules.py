## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import pytest

from joyfl.errors import JoyModuleError, JoyNameError
from joyfl.loader import iter_module_operators, _LIB_MODULES
from joyfl.runtime import Runtime


def _write(tmp_path, name, content):
    p = tmp_path / f"{name}.py"
    p.write_text(content, encoding="utf-8")
    return p


def _setup_env(monkeypatch, tmp_path):
    # Search only our temp dir for Python-backed Joy modules
    monkeypatch.setenv("JOY_PATH", str(tmp_path))
    # Ensure a fresh loader cache between tests
    _LIB_MODULES.clear()


def test_missing_operator_registry_raises_module_error(tmp_path, monkeypatch):
    # No __operators__ defined
    _write(tmp_path, "broken", "x = 1\n")
    _setup_env(monkeypatch, tmp_path)

    with pytest.raises(JoyModuleError) as e:
        list(iter_module_operators("broken", meta={"filename": "<test>", "line": 1, "column": 1}))

    assert "missing operator registry" in str(e.value).lower()
    assert e.value.joy_token == "broken"


def test_wrong_registry_type_raises_module_error(tmp_path, monkeypatch):
    # __operators__ exists but is not a list
    _write(tmp_path, "wrong", "__operators__ = 42\n")
    _setup_env(monkeypatch, tmp_path)

    with pytest.raises(JoyModuleError) as e:
        list(iter_module_operators("wrong", meta={"filename": "<test>"}))

    assert "missing operator registry" in str(e.value).lower()
    assert e.value.joy_token == "wrong"


def test_missing_operation_raises_name_error(tmp_path, monkeypatch):
    # Proper registry present but requested op doesn’t exist
    _write(tmp_path, "ok", "def op_present(x: int) -> int:\n    return x\n\n__operators__ = [op_present]\n")
    _setup_env(monkeypatch, tmp_path)

    with pytest.raises(JoyNameError) as e:
        Runtime().library.get_function("ok.absent", meta={"filename": "<test>"} )

    assert "not found in library" in str(e.value).lower()
    assert e.value.joy_token == "ok.absent"
