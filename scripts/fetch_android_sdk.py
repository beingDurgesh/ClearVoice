#!/usr/bin/env python3
"""Install Android cmdline-tools + required SDK packages into tools/android-sdk.

Downloads via urllib with retries (git/curl TLS is blocked in this sandbox).
Verifies zip integrity. Then runs sdkmanager for the packages the Gradle build
needs. Usage: python scripts/fetch_android_sdk.py [--packages "a" "b" ...]
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = ROOT / "tools" / "android-sdk"
CMDTOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
DEFAULT_PACKAGES = ["platform-tools", "platforms;android-35", "build-tools;35.0.0", "cmake;3.22.1"]
NDK_PACKAGE = "ndk;27.2.13479055"

JAVA_HOME = r"C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"


def download(url: str, dest: Path, retries: int = 6) -> Path:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
            with urllib.request.urlopen(req, timeout=900) as r:
                with open(dest, "wb") as f:
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        f.write(c)
            return dest
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt}/{retries} failed: {e}; retrying in 10s", flush=True)
            time.sleep(10)
    raise RuntimeError(f"download failed: {url}")


def main() -> int:
    packages = DEFAULT_PACKAGES + ([NDK_PACKAGE] if "--ndk" in sys.argv else [])
    if "--packages" in sys.argv:
        i = sys.argv.index("--packages")
        packages = sys.argv[i + 1:]

    SDK.mkdir(parents=True, exist_ok=True)
    tools_dir = SDK / "cmdline-tools"
    sdkmanager = tools_dir / "latest" / "bin" / "sdkmanager.bat"

    if not sdkmanager.exists():
        zpath = SDK / "cmdtools.zip"
        print(f"downloading cmdline-tools ({CMDTOOLS_URL}) ...", flush=True)
        download(CMDTOOLS_URL, zpath)
        with zipfile.ZipFile(zpath) as z:
            bad = z.testzip()
            assert bad is None, f"corrupt zip member: {bad}"
            z.extractall(tools_dir)
        # zip extracts to cmdline-tools/ -> move to cmdline-tools/latest
        inner = tools_dir / "cmdline-tools"
        if inner.exists():
            (tools_dir / "latest").mkdir(exist_ok=True)
            for item in inner.iterdir():
                item.rename(tools_dir / "latest" / item.name)
            inner.rmdir()
        zpath.unlink()
        print("cmdline-tools installed", flush=True)

    env_sdk = str(SDK)
    # accept licenses
    subprocess.run([str(sdkmanager), f"--sdk_root={env_sdk}", "--licenses"],
                   input="y\n" * 50, capture_output=True, text=True, timeout=600)
    print(f"installing packages: {packages}", flush=True)
    r = subprocess.run(
        [str(sdkmanager), f"--sdk_root={env_sdk}"] + packages,
        capture_output=True, text=True, timeout=7200,
        env={"JAVA_HOME": JAVA_HOME, "PATH": r"C:\Windows\System32;C:\Windows", "SystemRoot": r"C:\Windows"},
    )
    tail = (r.stdout or "")[-2000:]
    print(tail, flush=True)
    if r.returncode != 0:
        print(f"sdkmanager exit {r.returncode}: {(r.stderr or '')[-1000:]}", flush=True)
        return 1
    print("SDK READY at", SDK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
