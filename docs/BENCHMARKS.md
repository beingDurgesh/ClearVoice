# ClearVoice — benchmarks & measurements (Phase 5)

All numbers below were **measured on this machine on 2026-11-08** by running
`benchmarks/run_eval.py` and `benchmarks/measure_latency.py` against the real
`build/core/Release/clearvoice_core.dll`. Reproduce with:

```powershell
python benchmarks\make_test_signals.py   # deterministic synthetic WAVs -> benchmarks/data/
python benchmarks\run_eval.py             # denoise via DLL, SNR/SI-SDR -> results.json + results.md
python benchmarks\measure_latency.py      # impulse latency + CPU
```

Machine: Windows 11 26H2 x64, VS Build Tools 2022 (MSVC 14.44), Python 3.13.14.
Full tables: <benchmarks/results.md> (rendered from <benchmarks/results.json>).

## Headline measured results

| Metric | Measured value |
|---|---|
| Algorithmic latency (impulse through 48 kHz core) | **20.0 ms** (960 samples = 2 × 480-sample frames) |
| Core CPU cost (tight loop, incl. numpy/ctypes overhead) | **0.52% of one core** per second of audio |
| Live pipeline (real mic→speakers, 4 s) | 405 engine frames / 4 s, 0 input overflows, process CPU 9.4% |
| Fan noise (stationary) — noise-only reduction | **21.9 dB** |
| Traffic noise — noise-only reduction | **23.5 dB** |
| Speech + fan @ 0 dB SNR → output SNR | **18.9 dB** (+18.9 dB improvement) |
| Speech + traffic @ 0 dB SNR → output SNR | **19.5 dB** (+19.5 dB) |
| Speech + fan @ 10 dB → output SNR | 21.4 dB |
| Babble / 50 Hz hum / keyboard transients | ~0 dB change (voice/transient protection by design) |
| Clipping introduced by engine | 0 samples on all non-saturated inputs |

## Expected end-to-end latency (budget, not yet loopback-measured)

Core 20 ms + input buffer (~5–10 ms WASAPI shared) + output ring/buffer
(~5–10 ms) + cable (~few ms) ⇒ **expect ~35–50 ms end to end**.
The VB-CABLE impulse loopback measurement is **UNVERIFIED** here because the
driver is not installed in this sandbox — see `tools/hw_smoke.py` for the
in-machine variant and `docs/WINDOWS_SETUP.md` for the cable test.

## Methodology notes

- Test signals are **synthetic and deterministic** (seeded numpy): pseudo-speech
  (formant-shaped harmonics, syllable AM) mixed with fan/keyboard/babble/traffic/hum
  noise at 0/5/10 dB SNR. No downloaded samples; no invented numbers.
- Metrics: SNR and SI-SDR vs the clean reference after cross-correlation alignment;
  noise-only reduction = 10·log10(rms_in²/rms_out²); clipping = count of |x| ≥ 0.999.
- PESQ/STOI not used: PESQ needs a licensed tool; STOI would need an extra package —
  SNR/SI-SDR plus the before/after WAVs in `benchmarks/out/` (keep and listen) are
  the honest objective+subjective pair here. Listening tests remain manual.
