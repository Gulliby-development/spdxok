import importlib
import sys
import tomllib
from pathlib import Path

import pytest

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_project_scripts_registers_the_spdxok_command():
    manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["project"]["scripts"] == {"spdxok": "spdxok.__main__:run"}


def test_manifest_target_imports_safely_and_is_callable(monkeypatch, capsys):
    manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    target = manifest["project"]["scripts"]["spdxok"]
    module_name, function_name = target.split(":", maxsplit=1)
    calls = []

    def record_call(*args, **kwargs):
        calls.append((args, kwargs))

    cli = importlib.import_module("spdxok.cli")
    original_main = cli.main
    monkeypatch.setattr(cli, "main", record_call)
    monkeypatch.setattr(sys, "exit", record_call)
    monkeypatch.setattr(sys.stdout, "reconfigure", record_call, raising=False)
    monkeypatch.setattr(sys.stderr, "reconfigure", record_call, raising=False)

    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    entry_point = getattr(module, function_name)
    module.main = original_main

    assert callable(entry_point)
    assert calls == []
    assert capsys.readouterr() == ("", "")


def test_run_eval_writes_success_to_stdout(monkeypatch, capsys):
    from spdxok.__main__ import run

    monkeypatch.setattr("sys.argv", ["spdxok", "eval", "--allow", "MIT", "MIT OR GPL-3.0"])
    monkeypatch.setattr(sys.stdout, "reconfigure", lambda **_: None, raising=False)
    monkeypatch.setattr(sys.stderr, "reconfigure", lambda **_: None, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 0
    assert capsys.readouterr() == ("ok: uses MIT\n", "")


def test_run_without_arguments_writes_missing_command_to_stderr(monkeypatch, capsys):
    from spdxok.__main__ import run

    monkeypatch.setattr("sys.argv", ["spdxok"])
    monkeypatch.setattr(sys.stdout, "reconfigure", lambda **_: None, raising=False)
    monkeypatch.setattr(sys.stderr, "reconfigure", lambda **_: None, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    assert capsys.readouterr() == ("", "spdxok: missing command (eval, check or ids)\n")
