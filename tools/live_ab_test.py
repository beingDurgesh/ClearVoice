#!/usr/bin/env python3
"""Task 2a: live A/B test on a REAL input device — no GUI.

Captures N seconds from a chosen input device through the exact AudioPipeline
the GUI uses (real sounddevice streams; output plays at volume 0 so there is no
acoustic feedback, and the output callback is wrapped to record exactly what
would go to the virtual cable). Runs once with suppression ON (RNNoise) and
once OFF (passthrough), writes WAVs to benchmarks/out/, and prints per-second
RMS, the 10th-percentile frame RMS (noise floor), VAD, and the ON-vs-OFF
noise-floor difference in dB.

Usage:
    python tools/live_ab_test.py --device "Microphone" --seconds 8
"""
from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "windows"))

from audio.pipeline import AudioPipeline  # noqa: E402
from engine_binding.cv_core import CoreLib, CvEngineType  # noqa: E402


def pick_device(substr: str):
    import sounddevice as sd

    devs = list(sd.query_devices())
    hostapis = [h["name"] for h in sd.query_hostapis()]
    for i, d in enumerate(devs):
        if d["max_input_channels"] > 0 and substr.lower() in d["name"].lower():
            return i, d, hostapis[d["hostapi"]]
    raise SystemExit(
        f"no input device matching {substr!r}; available:\n"
        + "\n".join(
            f"  [{i}] {d['name']} in={d['max_input_channels']} rate={d['default_samplerate']} {hostapis[d['hostapi']]}"
            for i, d in enumerate(devs)
            if d["max_input_channels"] > 0
        )
    )


def capture(core, dev_idx, dev, seconds, engine, out_wav: Path, gain_db: float = 0.0) -> dict:
    import sounddevice as sd

    rate = int(dev["default_samplerate"]) or 48000
    out_idx = sd.default.device[1]
    recorded: list[np.ndarray] = []

    p = AudioPipeline(core)  # real sounddevice streams
    p.tap = lambda blk: recorded.append(blk)  # record pre-volume processed audio
    p.start(
        in_device=dev_idx, out_device=out_idx, in_name=dev["name"], out_name="default out",
        in_rate=rate, out_rate=rate, in_channels=1, out_channels=1,
        engine=engine, blocksize=512, dtype="float32", volume=0.0,  # volume 0: no feedback; tap sees raw
    )
    if gain_db:
        p.set_input_gain(gain_db)
    try:
        t0 = time.time()
        while time.time() - t0 < seconds:
            time.sleep(0.05)
        time.sleep(0.3)  # let the worker drain the tail
        x = np.concatenate(recorded) if recorded else np.zeros(0, np.float32)
        sr = 48000
        per_sec = []
        for s in range(int(seconds)):
            seg = x[s * sr:(s + 1) * sr]
            per_sec.append(round(20 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))), 1e-9)), 1) if len(seg) else -120.0)
        fl = 2400  # 50 ms frames
        frames = [x[i:i + fl] for i in range(0, len(x) - fl, fl)]
        frms = np.array([20 * np.log10(max(float(np.sqrt(np.mean(f ** 2))), 1e-9)) for f in frames])
        floor_db = float(np.percentile(frms, 10)) if len(frms) else -120.0
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        return {
            "engine": p.stats.engine_name,
            "wav": str(out_wav),
            "samples": int(len(x)),
            "per_second_dbfs": per_sec,
            "noise_floor_10pct_dbfs": round(floor_db, 1),
            "vad": round(p.stats.vad, 3),
            "frames_processed": p.stats.frames_processed,
            "peak_in_db": round(p.stats.peak_in_db, 1),
            "rms_db": round(float(20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-9))), 1) if len(x) else -120.0,
        }
    finally:
        p.stop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="Microphone")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--gain", type=float, default=0.0, help="extra phase: ON with this input gain (dB)")
    args = ap.parse_args()

    core = CoreLib()
    dev_idx, dev, api = pick_device(args.device)
    print(f"using [{dev_idx}] {dev['name']} ({api}, {dev['default_samplerate']} Hz)")

    phases = [("on", CvEngineType.RNNOISE, 0.0), ("off", CvEngineType.PASSTHROUGH, 0.0)]
    if args.gain:
        phases += [(f"on_gain{args.gain:g}", CvEngineType.RNNOISE, args.gain),
                   (f"off_gain{args.gain:g}", CvEngineType.PASSTHROUGH, args.gain)]
    results = {}
    for label, eng, gain in phases:
        wav = REPO / "benchmarks" / "out" / f"live_ab_{label}.wav"
        print(f"capturing {args.seconds:.0f}s: engine={eng.name} gain={gain:+.0f} dB ...")
        r = capture(core, dev_idx, dev, args.seconds, eng, wav, gain)
        results[label] = r
        print(f"  engine={r['engine']} peak_in={r['peak_in_db']} dBFS rms={r['rms_db']} dBFS "
              f"floor(10pct)={r['noise_floor_10pct_dbfs']} dBFS vad={r['vad']} frames={r['frames_processed']}")
        print(f"  per-second dBFS: {r['per_second_dbfs']}")
        print(f"  wrote {wav}")

    delta = results["off"]["noise_floor_10pct_dbfs"] - results["on"]["noise_floor_10pct_dbfs"]
    print(f"\nON-vs-OFF noise floor difference: {delta:+.1f} dB (positive = suppression works; ~0 = it doesn't)")
    if args.gain:
        og = results[f"on_gain{args.gain:g}"]
        fg = results[f"off_gain{args.gain:g}"]
        d2 = fg["noise_floor_10pct_dbfs"] - og["noise_floor_10pct_dbfs"]
        print(f"at +{args.gain:g} dB gain: ON-vs-OFF noise floor difference: {d2:+.1f} dB "
              f"(on_floor={og['noise_floor_10pct_dbfs']}, off_floor={fg['noise_floor_10pct_dbfs']}, vad_on={og['vad']})")
    print(f"peak input level (no gain): {results['on']['peak_in_db']} dBFS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
