"""Settings persistence: path resolution + atomic save/load."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import load_settings, resolve_config_path, save_settings


def test_override_env_used_when_non_empty():
    env = {"CLEARVOICE_CONFIG": "  C:\\custom\\cfg.json  ", "APPDATA": "C:\\appdata"}
    assert resolve_config_path(env) == Path("C:\\custom\\cfg.json")


def test_empty_override_falls_back_to_appdata():
    env = {"CLEARVOICE_CONFIG": "", "APPDATA": "C:\\Users\\x\\AppData\\Roaming"}
    p = resolve_config_path(env)
    assert p == Path("C:\\Users\\x\\AppData\\Roaming") / "ClearVoice" / "settings.json"
    assert str(p) != "."  # the old bug: Path("") == Path(".") caused Errno 13 on '.'


def test_empty_override_and_no_appdata_uses_home(monkeypatch, ws_tmp):
    monkeypatch.setenv("HOME", str(ws_tmp))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("CLEARVOICE_CONFIG", raising=False)
    p = resolve_config_path({})
    assert p.name == "settings.json"
    assert str(p) != "."


def test_save_load_roundtrip(ws_tmp):
    cfg = ws_tmp / "sub" / "settings.json"
    save_settings(cfg, {"engine": 1, "suppression": False, "input_device": 3})
    assert cfg.exists()
    assert load_settings(cfg) == {"engine": 1, "suppression": False, "input_device": 3}
    # atomic: no leftover .tmp
    assert not (ws_tmp / "sub" / "settings.json.tmp").exists()


def test_load_missing_returns_empty(ws_tmp):
    assert load_settings(ws_tmp / "nope.json") == {}


def test_save_refuses_directory_like_path():
    with pytest.raises(ValueError):
        save_settings(Path("."), {"a": 1})
    with pytest.raises(ValueError):
        save_settings(Path(""), {"a": 1})


def test_corrupt_file_returns_empty(ws_tmp):
    cfg = ws_tmp / "settings.json"
    cfg.write_text("{not json", encoding="utf-8")
    assert load_settings(cfg) == {}
