#!/usr/bin/env python3
"""ClearVoice Windows app entry point.

Usage:
    python windows/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the windows/ package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    from engine_binding.cv_core import CoreLib

    core = CoreLib()  # locates clearvoice_core.dll (env CLEARVOICE_DLL, frozen bundle, or build tree)
    print(f"ClearVoice core: {core.version()} ({core.path})")
    if "--version" in sys.argv:
        print(f"ClearVoice {core.version()}")
        return 0

    from PySide6.QtWidgets import QApplication

    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow(core)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
