"""Shared pytest fixtures: paths, env, DLL, offscreen Qt."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_DIR = REPO_ROOT / "windows"
for p in (str(WINDOWS_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Use the hash-verified wheels extracted into tools/pylibs (pip is blocked in this sandbox).
PYLIBS = REPO_ROOT / "tools" / "pylibs"
if PYLIBS.exists() and str(PYLIBS) not in sys.path:
    sys.path.insert(0, str(PYLIBS))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CLEARVOICE_DLL", str(REPO_ROOT / "build" / "core" / "Release" / "clearvoice_core.dll"))


@pytest.fixture(scope="session")
def core():
    from engine_binding.cv_core import CoreLib

    return CoreLib()


@pytest.fixture(scope="session")
def dll_path() -> Path:
    return Path(os.environ["CLEARVOICE_DLL"])


@pytest.fixture
def ws_tmp():
    """Workspace-local temp dir (the sandbox denies %TEMP% for pytest's tmp_path)."""
    d = REPO_ROOT / "build" / "pytest-tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def qapp():
    """Shared offscreen QApplication (QT_QPA_PLATFORM=offscreen is set above)."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
