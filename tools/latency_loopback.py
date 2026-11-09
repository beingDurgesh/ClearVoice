#!/usr/bin/env python3
"""End-to-end latency measurement through VB-CABLE (run on the user's machine).

Plays a short impulse into "CABLE Input" every 500 ms while recording from
"CABLE Output", cross-correlates each recorded impulse against the sent one,
and reports median end-to-end latency in ms (device buffers + cable + core).

Usage: python tools/latency_loopback.py --seconds 10
Requires VB-CABLE installed. In this sandbox the cable is absent -> UNVERIFIED.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "windows"))


def find_cable():
    import sounddevice as sd

    devs = list(sd.query_devices())
    play = rec = None
    for i, d in enumerate(devs):
        n = d["name"].lower()
        if "cable input" in n and d["max_output_channels"] > 0:
            play = i
        if "cable output" in n and d["max_input_channels"] > 0:
            rec = i
    if play is None or rec is None:
        raise SystemExit("VB-CABLE not found (need 'CABLE Input' output + 'CABLE Output' input). Install it first.")
    return play, rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()
    import sounddevice as sd

    play_idx, rec_idx = find_cable()
    rate = 48000
    block = 256
    impulse = np.zeros(64, dtype=np.float32)
    impulse[0] = 0.8
    sent_times: list[float] = []
    recorded: list[np.ndarray] = []

    def out_cb(outdata, frames, time_info, status):
        if len(sent_times) and (time.time() - sent_times[-1]) > 0.5:
            pass
        if not sent_times or (time.time() - sent_times[-1]) > 0.5:
            outdata[:] = 0
            outdata[: len(impulse), 0] = impulse
            sent_times.append(time.time())
        else:
            outdata[:] = 0

    def in_cb(indata, frames, time_info, status):
        recorded.append(indata[:, 0].copy())

    with sd.OutputStream(device=play_idx, samplerate=rate, channels=1, blocksize=block, dtype="float32", callback=out_cb), \
         sd.InputStream(device=rec_idx, samplerate=rate, channels=1, blocksize=block, dtype="float32", callback=in_cb):
        t0 = time.time()
        while time.time() - t0 < args.seconds:
            time.sleep(0.1)

    x = np.concatenate(recorded) if recorded else np.zeros(0, np.float32)
    lags = []
    for st in sent_times:
        # find the impulse echo: search a window around the sent time
        center = int(st * rate)
        lo, hi = max(0, center - rate // 10), min(len(x), center + rate)
        if hi - lo < 1024:
            continue
        seg = x[lo:hi]
        c = np.correlate(seg, impulse, mode="valid")
        if len(c) == 0:
            continue
        pk = int(np.argmax(np.abs(c)))
        if abs(c[pk]) > 0.05 * abs(impulse).max():
            lags.append((lo + pk - center) / rate * 1000.0)
    if not lags:
        print("no impulses detected — cable routing may be wrong")
        return 1
    lags = np.array(lags)
    print(f"detected {len(lags)} impulse echoes; latency ms: min={lags.min():.1f} median={np.median(lags):.1f} max={lags.max():.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
