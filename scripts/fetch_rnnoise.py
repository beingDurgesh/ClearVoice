#!/usr/bin/env python3
"""Vendor RNNoise (xiph/rnnoise) at a pinned commit into core/third_party/rnnoise.

Downloads each required file from raw.githubusercontent.com at the pinned SHA and
verifies both the byte size and the git blob SHA-1 (as reported by the GitHub git
tree API), so the vendored copy is provably identical to upstream.

Network calls are retried (CI runners sometimes hit SSL/handshake timeouts).

Usage:  python scripts/fetch_rnnoise.py
"""
from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST = REPO_ROOT / "core" / "third_party" / "rnnoise"
PINNED_SHA = "70f1d256acd4b34a572f999a05c87bf00b67730d"  # xiph/rnnoise main @ 2025-02-22 (verified signed commit)
BASE = f"https://raw.githubusercontent.com/xiph/rnnoise/{PINNED_SHA}/"

# path -> (git blob sha1, size)  taken from:
# https://api.github.com/repos/xiph/rnnoise/git/trees/main?recursive=1  (tree of PINNED_SHA)
FILES: dict[str, tuple[str, int]] = {
    "COPYING": ("59d7d09c80c17e60a972bf730caf6a3e005b17b1", 1612),
    "README": ("b8b2c461c38856525cb85262104f9788461e4a17", 6119),
    "include/rnnoise.h": ("81d8f62341ab39e51da0bd7332b905d79f36b782", 3825),
    "src/_kiss_fft_guts.h": ("17392b3e90977b74049049b7fa01a9f8cb0fc093", 6010),
    "src/arch.h": ("52de62334b71a7d07fac3daa4ae6c104d63d0718", 7628),
    "src/celt_lpc.c": ("750f9a8ae1a0fc803df2553926697ad9bf831faf", 4887),
    "src/celt_lpc.h": ("5abd61a0f84533478a27ea08017497361bbd529b", 1746),
    "src/common.h": ("f9095ca5e85ed8686f7af5c3e63dd963a726f52b", 1474),
    "src/cpu_support.h": ("9de21f3a4b963b64c0d0fcccf4c0e397e01cde31", 1776),
    "src/denoise.c": ("b6fc3d4a90e13184e5b94b892796a8288d8260db", 13964),
    "src/denoise.h": ("ccfecd9a7e2d6e0b337a93c29a9d1a8acb2b171a", 2284),
    "src/kiss_fft.c": ("97c4291756f1c5128fa0842bc38d23e88948825d", 16923),
    "src/kiss_fft.h": ("52387f21f9caaeb171559a23f20d0a6e57641c7c", 6335),
    "src/nnet.c": ("3cafea6051a858ba316a32478b59255863fb7222", 4444),
    "src/nnet.h": ("6b8023bdb03b9dfa49728a3dbe76c1f32bc8fc6d", 5638),
    "src/nnet_arch.h": ("dfd5eaadeaf6b8ee00257de58d0c114e32d52aa3", 9447),
    "src/nnet_default.c": ("4316f0fba3c5dca1085f46c5c97304ecbfb2e993", 1456),
    "src/opus_types.h": ("71808266655a1502105ea4c68f15e8ff0be932e4", 4954),
    "src/parse_lpcnet_weights.c": ("bdd50d7ea160a695741addf9126ad69fb646524b", 7528),
    "src/pitch.c": ("486a7fc4a70d11ed7e27e7833c7bf533649f4e95", 14085),
    "src/pitch.h": ("0a9d5e57f74e338865dd8e0423b760b22ac3ceb0", 4645),
    "src/rnn.c": ("b9472384a6751c1496229be2eb42be247839465f", 2912),
    "src/rnn.h": ("60a8871e7a89161e57c037cf89e2ecb6035269e3", 1850),
    "src/rnnoise_tables.c": ("adc8a28f451274bbd2156c13a3dfa883ac5d0f82", 56951),
    "src/vec.h": ("71b7afbb8b0289165155eff2c5956f23b8c605ed", 11167),
    "src/vec_avx.h": ("a5040b4596c89fde02d7fce5c2ed96eada1fb5ae", 25041),
    "src/vec_neon.h": ("31b736c3937ed000cefd3ab93c7ebcfb8d97ac3d", 13616),
    "src/x86/dnn_x86.h": ("bf1069867494e2b50662c4653606c91b6bd083d8", 3462),
    "src/x86/nnet_avx2.c": ("41037fcc89e2304ee0aa5b46a7814f7f4568f47d", 1575),
    "src/x86/nnet_sse4_1.c": ("224926e5a9754a6d28ab98d4fde2a3abea43410d", 1583),
    "src/x86/x86_arch_macros.h": ("975b443e9311fe015182b555a581d35b1cb0a936", 1618),
    "src/x86/x86_dnn_map.c": ("a16fa147f61867973cc9f3014ec9c637ed661b05", 2481),
    "src/x86/x86cpu.c": ("370c909be6dc91488566172577ee5efb6ce7d05e", 4760),
    "src/x86/x86cpu.h": ("e214abab547a8f6550163dd15bac5e5131a981db", 3456),
}

# The neural-network weights are distributed separately from the git repo
# (see upstream download_model.sh): a tarball on media.xiph.org whose sha256
# must equal the contents of the repo's `model_version` file.
MODEL_VERSION = "0a8755f8e2d834eff6a54714ecc7d75f9932e845df35f8b59bc52a7cfe6e8b37"
MODEL_URL = f"https://media.xiph.org/rnnoise/models/rnnoise_data-{MODEL_VERSION}.tar.gz"
MODEL_FILES = ["src/rnnoise_data.c", "src/rnnoise_data.h"]


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def download(url: str, timeout: int = 120, tries: int = 5) -> bytes | None:
    """GET url with retries and backoff. Returns bytes, or None after all tries fail."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt}/{tries} failed for {url}: {e}")
            if attempt < tries:
                time.sleep(5 * attempt)
    return None


def fetch_model() -> bool:
    print(f"model tarball: {MODEL_URL}")
    data = download(MODEL_URL, timeout=180, tries=5)
    if data is None:
        print("FAIL download model after all retries")
        return False
    digest = hashlib.sha256(data).hexdigest()
    if digest != MODEL_VERSION:
        print(f"FAIL model sha256 mismatch: {digest}")
        return False
    print(f"OK   model sha256 verified ({digest[:12]}...), {len(data)} bytes")

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in MODEL_FILES:
            f = tf.extractfile(member)
            if f is None:
                print(f"FAIL model tarball missing {member}")
                return False
            content = f.read()
            out = DEST / member
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
            print(f"OK   {member}  size={len(content)}")
    return True


def main() -> int:
    failures = 0
    if not fetch_model():
        failures += 1
    for rel, (want_sha, want_size) in sorted(FILES.items()):
        data = download(BASE + rel, timeout=60, tries=5)
        if data is None:
            print(f"FAIL download {rel}")
            failures += 1
            continue
        got_sha = git_blob_sha1(data)
        ok = got_sha == want_sha and len(data) == want_size
        status = "OK  " if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{status} {rel}  size={len(data)}/{want_size}  sha1={got_sha[:12]}")
        out = DEST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    total = len(FILES) + 1  # source files + model
    print(f"\n{total - failures}/{total} items vendored and verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())