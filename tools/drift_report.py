#!/usr/bin/env python3
"""Task 3: 5-minute (default) drift report on real devices.

Runs the real AudioPipeline for --seconds, samples buffer delay / glitch
counters / drift drops every second, writes a CSV to benchmarks/out/, and
prints slope + min/max/mean so clock drift between input and output devices is
visible (buffer growing => output clock slower than input clock).

Usage: python tools/drift_report.py --device "Microphone" --seconds 300
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "windows"))

from audio.pipeline import AudioPipeline  # noqa: E402
from engine_binding.cv_core import CoreLib, CvEngineType  # noqa: E402
from live_ab_test import pick_device  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="Microphone")
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--out", default=str(REPO / "benchmarks" / "out" / "drift_report.csv"))
    args = ap.parse_args()

    core = CoreLib()
    dev_idx, dev, api = pick_device(args.device)
    import sounddevice as sd

    out_idx = sd.default.device[1]
    rate = int(dev["default_samplerate"]) or 48000
    p = AudioPipeline(core)
    p.start(in_device=dev_idx, out_device=out_idx, in_name=dev["name"], out_name="default out",
            in_rate=rate, out_rate=rate, in_channels=1, out_channels=1,
            engine=CvEngineType.RNNOISE, blocksize=512, dtype="float32", volume=0.0)
    rows = []
    t0 = time.time()
    try:
        while time.time() - t0 < args.seconds:
            time.sleep(1.0)
            s = p.stats
            rows.append((round(time.time() - t0, 1), round(s.buffer_delay_ms, 1), s.in_overflow,
                         s.out_underflow, s.startup_underflow, s.steady_underflow, s.drift_drops,
                         round(s.cpu_percent, 2), round(s.peak_in_db, 1)))
    finally:
        p.stop()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "buffer_ms", "in_overflow", "out_underflow", "startup_underflow",
                    "steady_underflow", "drift_drops", "cpu_pct", "peak_in_db"])
        w.writerows(rows)
    buf = np.array([r[1] for r in rows])
    t = np.array([r[0] for r in rows])
    slope = float(np.polyfit(t, buf, 1)[0]) if len(rows) > 2 else 0.0
    print(f"samples: {len(rows)} over {args.seconds:.0f}s -> {out}")
    print(f"buffer delay ms: min={buf.min():.0f} mean={buf.mean():.0f} max={buf.max():.0f} slope={slope:+.3f} ms/s")
    last = rows[-1]
    print(f"final: in_overflow={last[2]} out_underflow={last[3]} (startup={last[4]} steady={last[5]}) drift_drops={last[6]} cpu={last[7]}%")
    print("interpretation: positive slope = output clock slower than input (ring grows; drift comp caps it at ~250 ms); "
          "steady_underflow>0 after startup = output faster than input (silence inserted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
