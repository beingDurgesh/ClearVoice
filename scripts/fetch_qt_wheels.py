#!/usr/bin/env python3
"""Download the three large PySide6 6.12.0 win_amd64 wheels (URLs pinned from PyPI
JSON fetched 2026-11-07) into tools/pylibs. Chunked download with retries; after
extraction every file is verified against the wheel's own RECORD hashes, and the
wheel sha256 is appended to tools/pylibs/WHEELS.sha256 for the record."""
import base64
import csv
import hashlib
import io
import time
import urllib.request
import zipfile
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "tools" / "pylibs"

WHEELS = [
    "https://files.pythonhosted.org/packages/02/41/ba3d52fe2acd942ebf71eb02b3bdf0897f7f6f4ce8f52289cb50228e48d3/pyside6_addons-6.12.0-cp310-abi3-win_amd64.whl",
    "https://files.pythonhosted.org/packages/03/61/9a7e32a37b224f68506785bfb0f288d516098ec71681782d72b695a6c95d/pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl",
    "https://files.pythonhosted.org/packages/2a/b6/bee97e7a2edeab72aafabb46ee5adc939790a638d107860b4cad7a20e407/shiboken6-6.12.0-cp310-abi3-win_amd64.whl",
]


def download(url: str) -> bytes:
    for attempt in range(1, 7):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
            with urllib.request.urlopen(req, timeout=900) as r:
                chunks = []
                while True:
                    c = r.read(1 << 20)
                    if not c:
                        break
                    chunks.append(c)
            return b"".join(chunks)
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt}/6 failed: {e}; retrying in 5s")
            time.sleep(5)
    raise RuntimeError(f"failed after retries: {url}")


def verify_record(zf: zipfile.ZipFile, name: str) -> None:
    record_name = next(n for n in zf.namelist() if n.endswith(".dist-info/RECORD"))
    bad = 0
    for row in csv.reader(io.TextIOWrapper(zf.open(record_name))):
        if len(row) < 2 or not row[1]:
            continue
        path, hash_spec = row[0], row[1]
        algo, _, b64 = hash_spec.partition("=")
        try:
            data = zf.read(path)
        except KeyError:
            continue
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        if digest != b64:
            print(f"  RECORD mismatch: {path}")
            bad += 1
    if bad:
        raise RuntimeError(f"{name}: {bad} files failed RECORD verification")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    log = DEST / "WHEELS.sha256"
    for url in WHEELS:
        name = url.rsplit("/", 1)[-1]
        print(f"downloading {name} ...", flush=True)
        data = download(url)
        sha = hashlib.sha256(data).hexdigest()
        with log.open("a") as f:
            f.write(f"{sha}  {name}\n")
        zf = zipfile.ZipFile(io.BytesIO(data))
        verify_record(zf, name)
        zf.extractall(DEST)
        print(f"OK {name} ({len(data)/1e6:.1f} MB, RECORD verified, extracted)", flush=True)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
