#!/usr/bin/env python3
"""Real-hardware smoke test for the Windows pipeline (no VB-CABLE needed).

Captures from the WASAPI microphone, runs the full native pipeline (resample ->
RNNoise -> output ring), and plays to the WASAPI speakers at volume 0.0 (so no
acoustic feedback) for a few seconds. Verifies frames processed, signal levels,
glitch counters and errors.

Usage: python tools/hw_smoke.py [seconds]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "windows"))

from audio.pipeline import AudioPipeline  # noqa: E402
from engine_binding.cv_core import CoreLib, CvEngineType  # noqa: E402


def pick_devices():
    import sounddevice as sd

    mic = spk = None
    for i, d in enumerate(sd.query_devices()):
        api = sd.query_hostapis()[d["hostapi"]]["name"]
        if api == "Windows WASAPI" and d["max_input_channels"] > 0 and int(d["default_samplerate"]) == 48000:
            mic = (i, d)
        if api == "Windows WASAPI" and d["max_output_channels"] > 0 and int(d["default_samplerate"]) == 48000:
            spk = (i, d)
    return mic, spk


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    mic, spk = pick_devices()
    if not mic or not spk:
        print("NO WASAPI 48k mic/speaker found — hardware test UNVERIFIED")
        return 2
    print(f"mic:  [{mic[0]}] {mic[1]['name']}")
    print(f"spk:  [{spk[0]}] {spk[1]['name']}")

    core = CoreLib()
    p = AudioPipeline(core)  # real sounddevice streams
    in_idx, in_dev = mic
    out_idx, out_dev = spk
    started = False
    for ch in (1, 2):
        try:
            p.start(
                in_device=in_idx, out_device=out_idx,
                in_name=in_dev["name"], out_name=out_dev["name"],
                in_rate=48000, out_rate=48000,
                in_channels=ch, out_channels=ch,
                engine=CvEngineType.RNNOISE, blocksize=512, dtype="float32",
                volume=0.0,  # no acoustic feedback
            )
            started = True
            print(f"pipeline started with {ch} channel(s)")
            break
        except Exception as e:
            print(f"open with {ch} ch failed: {e}")
            p.stop()
    if not started:
        print("FAILED to open streams — hardware test UNVERIFIED")
        return 2

    t0 = time.time()
    peak_in = -120.0
    while time.time() - t0 < seconds:
        time.sleep(0.2)
        peak_in = max(peak_in, p.stats.in_level_db)
    p.stop()
    s = p.stats
    print(f"ran {seconds:.1f}s")
    print(f"frames_processed = {s.frames_processed} (expect ~{int(seconds * 100)} for 10 ms frames)")
    print(f"engine = {s.engine_name}, in_rate = {s.in_rate}, out_rate = {s.out_rate}")
    print(f"peak input level = {peak_in:.1f} dBFS (mic noise floor expected around -60..-40)")
    print(f"last out level = {s.out_level_db:.1f} dBFS, vad = {s.vad:.3f}")
    print(f"in_overflow = {s.in_overflow}, out_overflow = {s.out_overflow}, out_underflow = {s.out_underflow}")
    print(f"worker cpu = {s.cpu_percent:.2f}%")
    print(f"error = {s.error}")
    ok = (
        s.frames_processed >= int(seconds * 50)
        and s.error is None
        and s.in_overflow == 0
        and s.out_underflow <= 480 * 3  # allow <= 3 frames of startup transient
    )
    print("HARDWARE SMOKE:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
