#!/usr/bin/env python3
"""Download pinned Python wheels via PyPI JSON API (urllib works where pip's temp
handling is blocked) and extract them into tools/pylibs for PYTHONPATH use.

Verifies each wheel's sha256 digest from the PyPI JSON before extracting.
Usage: python scripts/fetch_pywheels.py [pkg==ver ...]
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "tools" / "pylibs"

# name -> pinned version (None = latest)
PACKAGES: dict[str, str | None] = {
    "sounddevice": "0.5.6",
    "cffi": None,
    "pycparser": None,
    "PySide6": None,
    "PySide6_Addons": None,
    "PySide6_Essentials": None,
    "shiboken6": None,
}


def pick_wheel(files: list[dict]) -> dict | None:
    def rank(f: dict) -> tuple:
        fn = f["filename"]
        if "win_amd64" not in fn and "any" not in fn:
            return (9, 0)
        if "cp313" in fn:
            return (0, 0)
        if "abi3" in fn:
            return (1, 0)
        if "py3-none" in fn or "py2.py3-none" in fn:
            return (2, 0)
        return (5, 0)

    cands = [f for f in files if "win_amd64" in f["filename"] or f["filename"].endswith("any.whl")]
    if not cands:
        return None
    return sorted(cands, key=rank)[0]


def main() -> int:
    pkgs = sys.argv[1:] or [f"{k}=={v}" if v else k for k, v in PACKAGES.items()]
    failures = 0
    for spec in pkgs:
        name, _, ver = spec.partition("==")
        url = f"https://pypi.org/pypi/{name}/json" if not ver else f"https://pypi.org/pypi/{name}/{ver}/json"
        meta = None
        for attempt in range(1, 5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    meta = json.load(r)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  retry {attempt}/4 meta {name}: {e}")
        if meta is None:
            print(f"FAIL meta {name}")
            failures += 1
            continue
        version = meta["info"]["version"]
        wheel = pick_wheel(meta["urls"])
        if not wheel:
            print(f"FAIL {name}: no compatible wheel for {version}")
            failures += 1
            continue
        fn = wheel["filename"]
        want = wheel["digests"]["sha256"]
        print(f"{name} {version} <- {fn}")
        data = None
        for attempt in range(1, 5):
            try:
                with urllib.request.urlopen(wheel["url"], timeout=600) as r:
                    chunks = []
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        chunks.append(c)
                data = b"".join(chunks)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  retry {attempt}/4 for {fn}: {e}")
        if data is None:
            print(f"FAIL download {fn} after retries")
            failures += 1
            continue
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            print(f"FAIL sha256 mismatch {fn}: {got}")
            failures += 1
            continue
        DEST.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as z:
            z.extractall(DEST)
        print(f"OK   {fn} sha256 verified, extracted to tools/pylibs ({len(data)/1e6:.1f} MB)")
    print(f"\n{'FAILURES: %d' % failures if failures else 'ALL OK'} -> use: $env:PYTHONPATH='" + str(DEST) + "'")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
