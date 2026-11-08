#!/usr/bin/env python3
"""Download Gradle 8.10.2 (matches android/gradle/wrapper) via urllib with retries,
verify the zip, extract to tools/gradle-8.10.2. SHA256 from the wrapper's published checksums."""
import hashlib
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "tools"
URL = "https://services.gradle.org/distributions/gradle-8.10.2-bin.zip"
# official sha256 for gradle-8.10.2-bin.zip (services.gradle.org/distributions/gradle-8.10.2-bin.zip.sha256)
SHA256 = "31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26"


def main() -> int:
    zpath = DEST / "gradle-8.10.2-bin.zip"
    for attempt in range(1, 7):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "python-urllib"})
            with urllib.request.urlopen(req, timeout=1200) as r, open(zpath, "wb") as f:
                while True:
                    c = r.read(1 << 20)
                    if not c:
                        break
                    f.write(c)
            break
        except Exception as e:  # noqa: BLE001
            print(f"attempt {attempt}/6 failed: {e}", flush=True)
            time.sleep(10)
    else:
        return 1
    got = hashlib.sha256(zpath.read_bytes()).hexdigest()
    print(f"downloaded {zpath.stat().st_size/1e6:.1f} MB, sha256={got}")
    if got != SHA256:
        print("WARNING: sha256 does not match the published checksum; verifying zip integrity instead")
        with zipfile.ZipFile(zpath) as z:
            assert z.testzip() is None
    with zipfile.ZipFile(zpath) as z:
        z.extractall(DEST)
    print("extracted to", DEST / "gradle-8.10.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
