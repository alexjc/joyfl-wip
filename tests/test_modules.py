## joyfl — Copyright © 2025, Alex J. Champandard.  Licensed under AGPLv3; see LICENSE! ⚘

import pytest

import joyfl.api as J
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


def test_empty_operator_registry_is_valid(tmp_path, monkeypatch):
    # No __joy_operators__ defined — module loads but has no operators.
    _write(tmp_path, "empty", "x = 1\n")
    _setup_env(monkeypatch, tmp_path)

    ops = list(iter_module_operators("empty", meta={"filename": "<test>"}))
    assert ops == []


def test_wrong_registry_type_raises_module_error(tmp_path, monkeypatch):
    # __joy_operators__ exists but is not a list
    _write(tmp_path, "wrong", "__joy_operators__ = 42\n")
    _setup_env(monkeypatch, tmp_path)

    with pytest.raises(JoyModuleError) as e:
        list(iter_module_operators("wrong", meta={"filename": "<test>"}))

    assert "not a list" in str(e.value).lower()
    assert e.value.joy_token == "wrong"


def test_missing_operation_raises_name_error(tmp_path, monkeypatch):
    # Proper registry present but requested op doesn't exist
    _write(tmp_path, "ok", "def op_present(x: int) -> int:\n    return x\n\n__joy_operators__ = [op_present]\n")
    _setup_env(monkeypatch, tmp_path)

    with pytest.raises(JoyNameError) as e:
        Runtime().library.get_function("ok.absent", meta={"filename": "<test>"} )

    assert "not found in library" in str(e.value).lower()
    assert e.value.joy_token == "ok.absent"


def test_get_function_triggers_python_module_loading(tmp_path, monkeypatch):
    # Define a Python module with a single Joy operator `present`.
    _write(tmp_path, "ok",
        "def op_present(x: int) -> int: return x\n"
        "__joy_operators__ = [op_present]\n")
    _setup_env(monkeypatch, tmp_path)

    rt = Runtime()
    fn = rt.library.get_function("ok.present", meta={"filename": "<test>"})
    # The function should be registered under the fully-qualified Joy name.
    assert "ok.present" in rt.library.functions
    assert rt.library.functions["ok.present"] is fn


def test_python_module_registers_factory_via_api_and_is_auto_loaded(tmp_path, monkeypatch):
    # Python module imports the public API and registers a namespaced factory.
    module_source = (
        "import joyfl.api as J\n"
        "def op_dummy(x: int) -> int: return x\n"
        "J.register_factory('ok.answer', lambda: {'answer': 42})\n"
        "__joy_operators__ = [op_dummy]\n"
    )
    _write(tmp_path, "ok", module_source)
    _setup_env(monkeypatch, tmp_path)

    # First use of the factory name should trigger Python module loading.
    stack = J.run("@ok.answer .", filename="<USE>")
    top = J.from_stack(stack)[0]
    assert isinstance(top, dict) and top["answer"] == 42


def test_factory_auto_loaded_without_at_prefix(tmp_path, monkeypatch):
    # Factory used WITHOUT @ prefix should still auto-load the module.
    module_source = (
        "import joyfl.api as J\n"
        "def op_dummy(x: int) -> int: return x\n"
        "J.register_factory('nop.widget', lambda: {'widget': 99})\n"
        "__joy_operators__ = [op_dummy]\n"
    )
    _write(tmp_path, "nop", module_source)
    _setup_env(monkeypatch, tmp_path)

    # Use factory WITHOUT @ prefix — should still trigger auto-load.
    stack = J.run("nop.widget .", filename="<USE>")
    top = J.from_stack(stack)[0]
    assert isinstance(top, dict) and top["widget"] == 99


def test_package_module_with_submodule_import(tmp_path, monkeypatch):
    # Create a package (folder with __init__.py) that imports from a submodule.
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()

    # Submodule with helper function.
    (pkg_dir / "helpers.py").write_text(
        "def double(x): return x * 2\n",
        encoding="utf-8"
    )

    # __init__.py imports from submodule and exposes operator.
    (pkg_dir / "__init__.py").write_text(
        "from .helpers import double\n"
        "def op_twice(x: int) -> int: return double(x)\n"
        "__joy_operators__ = [op_twice]\n",
        encoding="utf-8"
    )
    _setup_env(monkeypatch, tmp_path)

    # Call the operator — should load the package and use the submodule.
    stack = J.run("7 pkg.twice .", filename="<USE>")
    assert J.from_stack(stack) == [14]
