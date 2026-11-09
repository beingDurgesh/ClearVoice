#!/usr/bin/env python3
"""Fetch the androidx compose/activity aars needed to typecheck MainActivity.kt
with plain kotlinc (no compose plugin needed for a typecheck)."""
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "tools" / "compose"
DEST.mkdir(parents=True, exist_ok=True)

AARS = [
    ("androidx/compose/ui/ui/1.7.6/ui-1.7.6.aar", "ui"),
    ("androidx/compose/ui/ui-graphics/1.7.6/ui-graphics-1.7.6.aar", "ui-graphics"),
    ("androidx/compose/ui/ui-unit/1.7.6/ui-unit-1.7.6.aar", "ui-unit"),
    ("androidx/compose/foundation/foundation/1.7.6/foundation-1.7.6.aar", "foundation"),
    ("androidx/compose/material3/material3/1.3.1/material3-1.3.1.aar", "material3"),
    ("androidx/compose/runtime/runtime/1.7.6/runtime-1.7.6.aar", "runtime"),
    ("androidx/activity/activity/1.9.3/activity-1.9.3.aar", "activity"),
    ("androidx/activity/activity-compose/1.9.3/activity-compose-1.9.3.aar", "activity-compose"),
]
JARS = [
    ("androidx/annotation/annotation/1.9.0/annotation-1.9.0.jar", "annotation.jar"),
]

for path, name in AARS:
    url = "https://dl.google.com/dl/android/maven2/" + path
    aar = DEST / (name + ".aar")
    if not aar.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
        aar.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    with zipfile.ZipFile(aar) as z:
        if "classes.jar" in z.namelist():
            z.extract("classes.jar", DEST / name)
            (DEST / name / "classes.jar").rename(DEST / (name + ".jar"))
        else:
            print("no classes.jar in", name, "(empty aar) — skipping")
            continue
    print("ok", name)

for path, name in JARS:
    url = "https://dl.google.com/dl/android/maven2/" + path
    out = DEST / name
    if not out.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
        out.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    print("ok", name)
print("DONE")
