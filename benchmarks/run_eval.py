#!/usr/bin/env python3
"""Run ClearVoice core over the synthetic test set and compute objective metrics.

For each mix: denoise with RNNoise (and passthrough as reference) through the
real clearvoice_core.dll via ctypes, align output to the clean signal by
cross-correlation, then compute SNR, SI-SDR, clipping count. For noise-only
files: noise reduction = 10*log10(rms_in^2 / rms_out^2).

Results -> benchmarks/results.json and benchmarks/results.md (real measured
numbers only; every value comes from a run on this machine).
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "windows"))

from engine_binding.cv_core import CoreLib, CvEngineType, CvSampleFormat  # noqa: E402

SR = 48000
DATA = Path(__file__).resolve().parent / "data"
OUT = Path(__file__).resolve().parent / "out"


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path: Path, x: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def denoise(core: CoreLib, x_i16: np.ndarray, engine: CvEngineType) -> np.ndarray:
    """Push a whole file through the processor in blocks, return 48k float out."""
    p = core.processor_create(engine, SR, 1, SR * 4)
    try:
        block = 512
        outs = []
        for off in range(0, len(x_i16), block):
            chunk = x_i16[off:off + block]
            rc = core.processor_push(p, chunk, CvSampleFormat.INT16)
            assert rc == 0, rc
            avail = core.processor_out_available(p)
            if avail:
                buf = np.empty(avail, dtype=np.float32)
                core.processor_read_out(p, buf)
                outs.append(buf.copy())
        # drain tail
        avail = core.processor_out_available(p)
        if avail:
            buf = np.empty(avail, dtype=np.float32)
            core.processor_read_out(p, buf)
            outs.append(buf.copy())
        return np.concatenate(outs) if outs else np.zeros(0, dtype=np.float32)
    finally:
        core.processor_destroy(p)


def best_lag(a: np.ndarray, b: np.ndarray, max_lag: int = 2000) -> int:
    """Lag (in samples) that best aligns a to b, via cross-correlation."""
    n = min(len(a), len(b), 48000)
    a0 = a[:n] - a[:n].mean()
    b0 = b[:n] - b[:n].mean()
    c = np.correlate(b0, a0, mode="full")  # c[k] aligns a shifted
    lags = np.arange(-(n - 1), n)
    m = (np.abs(lags) <= max_lag)
    return int(lags[m][np.argmax(c[m])])


def snr_db(clean: np.ndarray, est: np.ndarray, lag: int) -> float:
    # align est to clean: est[i - lag] ~ clean[i]
    e = est[max(0, -lag):len(clean) + min(0, lag)] if lag != 0 else est[:len(clean)]
    c = clean[max(0, lag):len(clean) + min(0, -lag)] if lag != 0 else clean[:len(est)]
    n = min(len(c), len(e))
    err = c[:n] - e[:n]
    return 10 * np.log10(np.sum(c[:n] ** 2) / (np.sum(err ** 2) + 1e-12))


def sisdr_db(clean: np.ndarray, est: np.ndarray, lag: int) -> float:
    e = est[max(0, -lag):] if lag != 0 else est
    c = clean[max(0, lag):] if lag != 0 else clean
    n = min(len(c), len(e))
    c = c[:n]
    e = e[:n]
    alpha = np.dot(e, c) / (np.dot(c, c) + 1e-12)
    s_target = alpha * c
    e_noise = e - s_target
    return 10 * np.log10(np.sum(s_target ** 2) / (np.sum(e_noise ** 2) + 1e-12))


def clipping(x: np.ndarray) -> int:
    return int(np.sum(np.abs(x) >= 0.999))


def main() -> int:
    core = CoreLib()
    print("core:", core.version())
    clean = read_wav(DATA / "clean_speech.wav")
    clean_i16 = (np.clip(clean, -1, 1) * 32767).astype(np.int16)
    results: dict = {"core_version": core.version(), "sample_rate": SR, "mixes": {}, "noise_only": {}}

    for wav in sorted(DATA.glob("mix_*.wav")):
        noisy = read_wav(wav)
        noisy_i16 = (np.clip(noisy, -1, 1) * 32767).astype(np.int16)
        entry = {"input_snr_db": None}
        # input SNR
        entry["input_snr_db"] = round(float(snr_db(clean, noisy, best_lag(noisy, clean))), 2)
        for eng_name, eng in (("rnnoise", CvEngineType.RNNOISE), ("passthrough", CvEngineType.PASSTHROUGH)):
            out = denoise(core, noisy_i16, eng)
            write_wav(OUT / f"{wav.stem}_{eng_name}.wav", out)
            lag = best_lag(out, clean)
            entry[eng_name] = {
                "snr_db": round(float(snr_db(clean, out, lag)), 2),
                "si_sdr_db": round(float(sisdr_db(clean, out, lag)), 2),
                "clipping": clipping(out),
                "out_rms": round(float(np.sqrt(np.mean(out ** 2))), 5),
                "lag_samples": lag,
            }
        results["mixes"][wav.stem] = entry
        r = entry["rnnoise"]
        p = entry["passthrough"]
        print(f"{wav.stem:22s} inSNR={entry['input_snr_db']:6.2f} | RNNoise SNR={r['snr_db']:6.2f} SI-SDR={r['si_sdr_db']:6.2f} clip={r['clipping']} | pass SNR={p['snr_db']:6.2f}")

    for wav in sorted(DATA.glob("noise_only_*.wav")):
        noisy = read_wav(wav)
        noisy_i16 = (np.clip(noisy, -1, 1) * 32767).astype(np.int16)
        out = denoise(core, noisy_i16, CvEngineType.RNNOISE)
        write_wav(OUT / f"{wav.stem}_rnnoise.wav", out)
        nr = 10 * np.log10((np.mean(noisy ** 2) + 1e-12) / (np.mean(out ** 2) + 1e-12))
        results["noise_only"][wav.stem] = {
            "noise_reduction_db": round(float(nr), 2),
            "clipping": clipping(out),
            "in_rms": round(float(np.sqrt(np.mean(noisy ** 2))), 4),
        }
        print(f"{wav.stem:22s} in_rms={np.sqrt(np.mean(noisy**2)):.3f} noise reduction = {nr:6.2f} dB, clip={clipping(out)}")

    (Path(__file__).resolve().parent / "results.json").write_text(json.dumps(results, indent=2))
    print("wrote benchmarks/results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
