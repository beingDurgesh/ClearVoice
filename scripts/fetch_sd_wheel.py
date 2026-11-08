#!/usr/bin/env python3
"""Fetch the sounddevice 0.5.6 win_amd64 wheel (bundles PortAudio) into tools/pylibs.
URL pinned from PyPI JSON (2026-11-07); integrity via the wheel's RECORD hashes."""
import base64
import csv
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "tools" / "pylibs"
URL = "https://files.pythonhosted.org/packages/8d/3e/cbc593c31a5f0d817b3fe97e64aa8461bd0f55cb07b67ce1b776296ae336/sounddevice-0.5.6-py3-none-win_amd64.whl"

req = urllib.request.Request(URL, headers={"User-Agent": "python-urllib"})
with urllib.request.urlopen(req, timeout=300) as r:
    data = b""
    while True:
        c = r.read(1 << 20)
        if not c:
            break
        data += c
sha = hashlib.sha256(data).hexdigest()
(DEST / "WHEELS.sha256").parent.mkdir(parents=True, exist_ok=True)
with (DEST / "WHEELS.sha256").open("a") as f:
    f.write(f"{sha}  sounddevice-0.5.6-py3-none-win_amd64.whl\n")
zf = zipfile.ZipFile(io.BytesIO(data))
record_name = next(n for n in zf.namelist() if n.endswith(".dist-info/RECORD"))
bad = 0
for row in csv.reader(io.TextIOWrapper(zf.open(record_name))):
    if len(row) < 2 or not row[1]:
        continue
    path, hash_spec = row[0], row[1]
    _, _, b64 = hash_spec.partition("=")
    try:
        d = zf.read(path)
    except KeyError:
        continue
    if base64.urlsafe_b64encode(hashlib.sha256(d).digest()).rstrip(b"=").decode() != b64:
        bad += 1
assert bad == 0, f"{bad} RECORD mismatches"
zf.extractall(DEST)
print(f"OK sounddevice win_amd64 wheel ({len(data)/1e6:.2f} MB, RECORD verified) sha256={sha}")
