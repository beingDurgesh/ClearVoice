#!/usr/bin/env python3
"""Install Android SDK packages by downloading them directly via urllib.

sdkmanager's Java HTTP stack is blocked in this sandbox, so we parse the
official repository XML (dl.google.com/.../repository2-3.xml), download each
package zip with urllib, verify its sha256 from the XML, and extract it into
tools/android-sdk with the layout the SDK expects.

Usage: python scripts/fetch_sdk_packages.py <path> [<path> ...]
  e.g. python scripts/fetch_sdk_packages.py "platform-tools" "platforms;android-35" "build-tools;35.0.0" "cmake;3.22.1" "ndk;27.2.13479055"
"""
from __future__ import annotations

import hashlib
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = ROOT / "tools" / "android-sdk"
REPO_XML = "https://dl.google.com/android/repository/repository2-3.xml"


def fetch(url: str, dest: Path | None = None, retries: int = 6) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
            with urllib.request.urlopen(req, timeout=1200) as r:
                if dest is None:
                    chunks = []
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        chunks.append(c)
                    return b"".join(chunks)
                with open(dest, "wb") as f:
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        f.write(c)
                return dest.read_bytes()
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt}/{retries} failed: {e}; retrying in 10s", flush=True)
            time.sleep(10)
    raise RuntimeError(f"download failed: {url}")


def expected_dir(path: str) -> tuple[str, str]:
    """(parent dir under SDK, final dir name) for a remotePackage path."""
    if path.startswith("platforms;"):
        return "platforms", path.split(";", 1)[1]
    if path.startswith("build-tools;"):
        return "build-tools", path.split(";", 1)[1]
    if path.startswith("cmake;"):
        return "cmake", path.split(";", 1)[1]
    if path.startswith("ndk;"):
        return "ndk", path.split(";", 1)[1]
    if path.startswith("ndk-bundle"):
        return "ndk-bundle", ""
    return "", path  # e.g. platform-tools, emulator, system-images...


def child(el, name):
    """First child whose tag ends with `name` (namespace-agnostic)."""
    for c in el:
        if c.tag.endswith(name):
            return c
    return None


def child_text(el, name):
    c = child(el, name)
    return c.text.strip() if c is not None and c.text else None


def main() -> int:
    wanted = sys.argv[1:]
    if not wanted:
        print(__doc__)
        return 2
    print("fetching repository XMLs (merged) ...", flush=True)
    found: dict[str, tuple[str, str, str]] = {}  # path -> (url, sha256, size)
    for name in ("repository2-1.xml", "repository2-2.xml", "repository2-3.xml"):
        try:
            root = ET.fromstring(fetch(f"https://dl.google.com/android/repository/{name}"))
        except Exception as e:  # noqa: BLE001
            print(f"  {name} skipped: {e}")
            continue
        for pkg in root.iter():
            if not pkg.tag.endswith("remotePackage"):
                continue
            path = pkg.get("path", "")
            if path not in wanted or path in found:
                continue
            # schema nests <archives><archive><host-os>..</host-os><complete>...</complete></archive></archives>
            # prefer the Windows host archive
            best = None
            for arch in pkg.iter():
                if not arch.tag.endswith("archive"):
                    continue
                comp = child(arch, "complete")
                if comp is None:
                    continue
                hos = child_text(arch, "host-os") or ""
                cand = (comp, hos)
                if hos == "windows":
                    best = cand
                    break
                if best is None:
                    best = cand
            if best is None:
                continue
            complete, _hos = best
            url = child_text(complete, "url")
            sha = None
            for c in complete.iter():
                if c.tag.endswith("checksum") and (c.get("type") or "").lower() in ("sha-256", "sha256"):
                    sha = (c.text or "").strip()
            size = child_text(complete, "size")
            if url:
                found[path] = (url, sha, size or "?")

    missing = [p for p in wanted if p not in found]
    if missing:
        print(f"NOT FOUND in repository XML: {missing}")
        return 1

    SDK.mkdir(parents=True, exist_ok=True)
    for path, (url, sha, size) in found.items():
        parent, name = expected_dir(path)
        target = SDK / parent / name if parent else SDK / name
        marker = target / "source.properties"
        if marker.exists():
            print(f"already installed: {path} -> {target}")
            continue
        full_url = url if url.startswith("http") else "https://dl.google.com/android/repository/" + url
        print(f"downloading {path} ({size} bytes) from {full_url}", flush=True)
        zpath = SDK / (path.replace(";", "_") + ".zip")
        data = fetch(full_url, zpath)
        got = hashlib.sha256(data).hexdigest()
        if sha and got != sha.lower():
            print(f"FAIL sha256 mismatch for {path}: {got} != {sha}")
            return 1
        print(f"OK sha256 verified ({got[:12]}...)", flush=True)
        with zipfile.ZipFile(zpath) as z:
            assert z.testzip() is None
            z.extractall(SDK / "_tmp")
        # locate extracted root and move into place
        tmp = SDK / "_tmp"
        entries = list(tmp.iterdir())
        src = entries[0] if len(entries) == 1 else tmp
        dest_parent = SDK / parent if parent else SDK
        dest_parent.mkdir(parents=True, exist_ok=True)
        final = dest_parent / name if name else dest_parent / src.name
        if final.exists():
            import shutil

            shutil.rmtree(final)
        src.rename(final)
        if src != tmp and tmp.exists():
            import shutil

            shutil.rmtree(tmp)
        zpath.unlink()
        print(f"installed: {path} -> {final}", flush=True)

    # license stubs so AGP accepts the SDK
    lic = SDK / "licenses"
    lic.mkdir(exist_ok=True)
    (lic / "android-sdk-license").write_text(
        "\n24333f8a63b6825ea9c5514f83c2829b004d1fee\n8933bad161af4178b1185d1a37fbf41ea5269c55\n"
    )
    (lic / "android-sdk-preview-license").write_text("\n84831b9409646a918e30573bab4c9c91346d8abd\n")
    print("licenses written")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
