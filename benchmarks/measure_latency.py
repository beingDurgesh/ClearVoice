#!/usr/bin/env python3
"""Measure the core's offline processing latency and CPU cost (real numbers).

- Latency: impulse through the 48 kHz processor -> first significant output
  sample delay = algorithmic latency (frame delay + pipeline buffering).
- CPU: time to process 30 s of audio (process_time) -> % of one core.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "windows"))

from engine_binding.cv_core import CoreLib, CvEngineType, CvSampleFormat  # noqa: E402

SR = 48000


def main() -> int:
    core = CoreLib()
    p = core.processor_create(CvEngineType.RNNOISE, SR, 1, SR * 4)
    try:
        # ---- latency: impulse ----
        n = SR  # 1 s
        imp = np.zeros(n, dtype=np.int16)
        imp[1000] = 30000
        block = 512
        outs = []
        for off in range(0, n, block):
            core.processor_push(p, imp[off:off + block], CvSampleFormat.INT16)
            avail = core.processor_out_available(p)
            if avail:
                buf = np.empty(avail, dtype=np.float32)
                core.processor_read_out(p, buf)
                outs.append(buf.copy())
        out = np.concatenate(outs)
        nz = np.nonzero(np.abs(out) > 0.005)[0]
        if len(nz) == 0:
            print("no output — latency UNMEASURABLE")
            return 1
        delay_samples = int(nz[0])
        print(f"impulse at sample 1000 -> first output at {delay_samples}")
        print(f"algorithmic latency = {delay_samples - 1000} samples = {(delay_samples - 1000) / SR * 1000:.2f} ms")

        # ---- CPU: process 30 s of noise ----
        p2 = core.processor_create(CvEngineType.RNNOISE, SR, 1, SR * 4)
        rng = np.random.default_rng(5)
        total = SR * 30
        chunk = (rng.standard_normal(total) * 8000).astype(np.int16)
        t0 = time.perf_counter()
        c0 = time.process_time()
        for off in range(0, total, block):
            core.processor_push(p2, chunk[off:off + block], CvSampleFormat.INT16)
            avail = core.processor_out_available(p2)
            if avail:
                buf = np.empty(avail, dtype=np.float32)
                core.processor_read_out(p2, buf)
        wall = time.perf_counter() - t0
        cpu = time.process_time() - c0
        audio_s = total / SR
        print(f"processed {audio_s:.1f} s of audio in {wall:.3f} s wall, {cpu:.3f} s CPU")
        print(f"real-time CPU cost = {100 * cpu / audio_s:.3f}% of one core (tight loop, incl. numpy/ctypes overhead)")
        print(f"(in a live app the worker sleeps when idle; this is the worst-case busy-loop figure)")
        core.processor_destroy(p2)
    finally:
        core.processor_destroy(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
