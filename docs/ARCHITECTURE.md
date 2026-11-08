# ClearVoice — Architecture (as implemented in Phase 2)

## Component diagram

```
┌──────────────────────────┐                 ┌────────────────────────────┐
│ Windows GUI (Phase 3)    │  ctypes         │ Android app (Phase 4)      │  JNI
│ PySide6 + sounddevice    │──────────────►  │ Kotlin/Compose + AudioRecord│──────►
└──────────────────────────┘                 └────────────────────────────┘
                    │                                        │
                    ▼                                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ core/  →  clearvoice_core.dll (Windows, MSVC)  /  libclearvoice_core.so   │
│           (Android, NDK clang)                                            │
│                                                                           │
│  CvProcessor:                                                             │
│    push(interleaved PCM)                                                  │
│      → convertToMonoF32 (int16/int32/float32, N ch → mono float32)        │
│      → Resampler (windowed-sinc, table-driven, any rate → 48 kHz)         │
│      → FrameFifo (accumulate arbitrary blocks → 480-sample frames)        │
│      → IEngine::processFrame (RNNoise | Passthrough)  → vad probability   │
│      → RingBuffer (lock-free SPSC) → readOut() by the real-time thread    │
└──────────────────────────────────────────────────────────────────────────┘
```

## Threading contract

- The PortAudio/AudioRecord callback thread only does `memcpy` into/out of the
  lock-free ring (`cv_ring_write` / `cv_ring_read_padded`).
- All DSP runs on one worker thread via `cv_processor_push`.
- No allocation, logging, locking, or I/O inside the real-time callback.
- Glitches are counted, never hidden: `cv_ring_overflow_count` (producer dropped
  newest on full) and `cv_ring_underflow_count` (consumer zero-filled on empty).
- No C++ exception crosses the C API (every entry point is wrapped in try/catch).

## Key formats

- Engine internal format: **48,000 Hz, mono, float32, 480 samples/frame (10 ms)**
  (frame size read at runtime via `rnnoise_get_frame_size()`, never hardcoded).
- Input accepted: any sample rate, 1–8 channels, int16/int32/float32 interleaved.
- Resampler: Kaiser-windowed sinc, H=24 half-taps, 512-phase table, anti-alias
  cutoff `0.5·min(1, out/in)·0.95` of input Nyquist. Fixed group delay of
  `H-1` input samples. Measured SNR vs analytic ideal (this machine, 2026-11-07):
  44.1k→48k 1 kHz sine **76.3 dB**, 48k→16k **88.0 dB**, 16k→48k 500 Hz **73.3 dB**.
- 48k→48k is a pure passthrough (no resampling cost).

## Measured engine behavior (this machine, 2026-11-07, x64 Release build)

- `rnnoise_get_frame_size()` = **480**, `rnnoise_get_size()` = **32,688 bytes**.
- Loud white noise (uniform ±0.9): settled attenuation **~4.4–5.7 dB**, VAD ≈ 0.01.
  RNNoise is intentionally conservative — it removes steady noise, keeps voice.
- Below the internal silence threshold (frame energy E < 0.04) RNNoise passes the
  (delayed) frame through unchanged by design — very quiet input is left alone.
- RNNoise has a built-in **one-frame (10 ms) delay** (it outputs the previous
  frame's spectrum scaled by the current gains).

## Files

| Path | Purpose |
|---|---|
| `core/include/clearvoice/clearvoice.h` | Public C API (contract for ctypes + JNI) |
| `core/src/engine.{h,cpp}` | `IEngine` + `RnNoiseEngine` + `PassthroughEngine` |
| `core/src/resampler.{h,cpp}` | Streaming windowed-sinc resampler |
| `core/src/convert.{h,cpp}` | Interleaved PCM → mono float32 |
| `core/src/frame_fifo.{h,cpp}` | Arbitrary blocks → fixed frames |
| `core/src/ring_buffer.{h,cpp}` | Lock-free SPSC ring buffer |
| `core/src/processor.{h,cpp}` | Full pipeline (convert→resample→fifo→engine→ring) |
| `core/src/c_api.cpp` | `extern "C"` wrappers, exception-safe |
| `core/third_party/rnnoise/` | Vendored RNNoise, pinned + hash-verified (`third_party/PINNED.md`) |
| `core/tests/` | 27 unit tests (own tiny framework, no deps) |
| `scripts/fetch_rnnoise.py` | Reproducible, hash-verified vendoring |
| `tools/smoke_dll.py` | ctypes smoke test against the built DLL |
| `tools/debug_rnnoise.c` | Direct upstream-RNNoise probe (diagnostics) |

## Build & test (Windows, verified 2026-11-07)

```powershell
# CMake ships with VS Build Tools 2022:
$cm = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
& $cm -S core -B build\core -G "Visual Studio 17 2022" -A x64
& $cm --build build\core --config Release
.\build\core\Release\cv_tests.exe        # 27 tests
python tools\smoke_dll.py                 # ctypes FFI smoke test
```

Android (Phase 4) reuses the same `core/CMakeLists.txt` with the NDK toolchain.
