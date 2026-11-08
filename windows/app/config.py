"""Settings persistence for the ClearVoice Windows app.

Path resolution (in priority order):
  1. $CLEARVOICE_CONFIG (only if non-empty after stripping)
  2. %APPDATA%\\ClearVoice\\settings.json on Windows
  3. ~/.clearvoice/settings.json elsewhere

Writes are atomic (temp file + os.replace) and failures are raised to the
caller, which logs them once.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


def resolve_config_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get("CLEARVOICE_CONFIG", "").strip()
    if override:
        return Path(override)
    appdata = env.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "ClearVoice" / "settings.json"
    return Path.home() / ".clearvoice" / "settings.json"


def save_settings(path: Path | str, data: Mapping) -> None:
    path = Path(path)
    if str(path) in ("", "."):
        raise ValueError(f"refusing to write settings to directory-like path: {path!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(dict(data), indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic on same filesystem


def load_settings(path: Path | str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}
