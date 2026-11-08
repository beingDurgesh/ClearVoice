#!/usr/bin/env python3
"""Generate deterministic synthetic test signals for ClearVoice evaluation.

All signals are 48 kHz mono 16-bit WAV, written to benchmarks/data/.
Signals are SYNTHETIC (clearly labelled) — pseudo-speech (harmonics with
formant-shaped spectrum, syllable AM) mixed with fan/keyboard/babble/traffic/hum
noise at controlled SNR. No external samples are downloaded.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(__file__).resolve().parent / "data"


def write_wav(name: str, x: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    y = np.clip(x, -1.0, 1.0)
    pcm = (y * 32767).astype(np.int16)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote data/{name}  ({len(x)/SR:.2f}s, rms={np.sqrt(np.mean(y**2)):.4f})")


def pseudo_speech(dur: float, seed: int = 7) -> np.ndarray:
    """Deterministic pseudo-speech: pitch ~110-140 Hz with jitter, harmonics
    shaped by three formants (~500/1500/2500 Hz), 4 Hz syllable amplitude."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    pitch = 120 + 15 * np.sin(2 * np.pi * 0.7 * t) + rng.standard_normal(n).cumsum() * 0.0
    phase = np.cumsum(2 * np.pi * pitch / SR)
    formants = [(500, 1.0), (1500, 0.6), (2500, 0.35)]
    x = np.zeros(n)
    for k in range(1, 25):  # harmonics
        f = k * pitch
        g = sum(a * np.exp(-0.5 * ((f - fc) / 180.0) ** 2) for fc, a in formants)
        x += (g / k) * np.sin(k * phase + rng.uniform(0, 0.3))
    syl = 0.55 + 0.45 * np.sin(2 * np.pi * 4.0 * t)  # syllables
    env = np.clip(syl, 0.05, 1.0)
    x = x * env
    x /= np.max(np.abs(x)) / 0.7  # normalize to -3 dBFS peak
    return x.astype(np.float32)


def brown_noise(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    b = np.cumsum(w)
    b -= np.linspace(b[0], b[-1], n)  # remove drift
    return b / (np.max(np.abs(b)) + 1e-9)


def onepole_lp(x: np.ndarray, fc: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = a * acc + (1 - a) * x[i]
        y[i] = acc
    return y


def fan_noise(dur: float, seed: int = 1) -> np.ndarray:
    n = int(dur * SR)
    return onepole_lp(brown_noise(n, seed), 400.0).astype(np.float32)


def hum(dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (0.5 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 100 * t) + 0.2 * np.sin(2 * np.pi * 150 * t)).astype(np.float32)


def keyboard_noise(dur: float, seed: int = 2) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n, dtype=np.float32)
    n_clicks = int(dur * 6)  # ~6 clicks/sec
    for _ in range(n_clicks):
        i = rng.integers(0, n - 200)
        L = int(rng.integers(30, 200))
        x[i:i + L] += rng.standard_normal(L).astype(np.float32) * np.exp(-np.arange(L) / 25.0)
    return x


def babble(dur: float, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, dtype=np.float32)
    for v in range(5):
        f0 = rng.uniform(150, 320)
        am = rng.uniform(3, 6)
        ph = 2 * np.pi * f0 * t + rng.uniform(0, 6)
        voice = sum((1.0 / k) * np.sin(k * ph) for k in range(1, 8))
        x += voice * (0.5 + 0.5 * np.sin(2 * np.pi * am * t + rng.uniform(0, 6)))
    return x / (np.max(np.abs(x)) + 1e-9)


def traffic_noise(dur: float, seed: int = 4) -> np.ndarray:
    n = int(dur * SR)
    x = onepole_lp(brown_noise(n, seed), 250.0)
    t = np.arange(n) / SR
    am = 0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t) * np.sin(2 * np.pi * 0.13 * t + 1.0)
    return (x * am).astype(np.float32)


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    n = min(len(speech), len(noise))
    s = speech[:n]
    nz = noise[:n]
    nz = nz / (np.sqrt(np.mean(nz ** 2)) + 1e-9)
    target_rms = np.sqrt(np.mean(s ** 2))
    nz = nz * (target_rms / (10 ** (snr_db / 20)))
    return (s + nz).astype(np.float32)


def main() -> None:
    dur = 6.0
    speech = pseudo_speech(dur)
    write_wav("clean_speech.wav", speech)
    noises = {
        "fan": fan_noise(dur, 11),
        "keyboard": keyboard_noise(dur, 12),
        "babble": babble(dur, 13),
        "traffic": traffic_noise(dur, 14),
        "hum": hum(dur),
    }
    for name, nz in noises.items():
        # noise-only at a realistic level: normalized to RMS 0.2 (~-14 dBFS)
        nz_n = nz / (np.sqrt(np.mean(nz ** 2)) + 1e-9) * 0.2
        write_wav(f"noise_only_{name}.wav", nz_n)
        for snr in (0, 5, 10):
            write_wav(f"mix_{name}_{snr}db.wav", mix_at_snr(speech, nz, snr))
    print("all test signals written to", OUT)


if __name__ == "__main__":
    main()
