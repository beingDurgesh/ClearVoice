# ClearVoice — Phase 1: Technical Investigation & Architecture Proposal

**Date:** 2026-11-07 · **Status:** awaiting user approval before implementation
**Investigated on:** Windows 11 26H2 (build 10.0.26300), Python 3.13.14, VS Build Tools 2022 (MSVC 14.44.35207, Windows SDK 10.0.26100.0)

All facts below were verified against official sources on 2026-11-07 (URLs cited). Where something could not be verified, it is marked **[UNVERIFIED]**.

---

## 0. What this machine can already do (verified locally)

| Tool | Status |
|---|---|
| Windows 11 26H2 x64 | ✅ build 10.0.26300 |
| Python 3.13.14 + pip 26.2.1 | ✅ (`python`, `pip`) |
| numpy 2.3.2 | ✅ installed |
| sounddevice, PySide6 | ❌ not installed yet (pip-installable) |
| MSVC `cl.exe` 14.44.35207 (VS Build Tools 2022) | ✅ at `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe` |
| Windows SDK 10.0.26100.0 | ✅ |
| CMake | ❌ not installed (fix: `pip install cmake`) |
| MinGW gcc 6.3.0 | ⚠️ present but too old — do not use |
| Node.js v22.23.1 | ✅ |
| Java 25 (JDK) | ✅ |
| Android SDK / NDK | ❌ not installed (needed in Phase 4; install Android Studio cmdline-tools + NDK) |
| VB-CABLE virtual audio driver | ❌ not installed yet (needed for Windows virtual mic) |

**Consequence:** we can compile native C/C++ on this machine today with MSVC, and install everything else with pip. Android work needs an SDK install later.

---

## 1. Noise-suppression technology comparison (verified against official sources)

| Criterion | **RNNoise** (xiph/rnnoise) | **WebRTC Audio Processing** | **DeepFilterNet** (Rikorose) | **Android NoiseSuppressor** |
|---|---|---|---|---|
| What it is | RNN (GRU) denoiser, 480-sample frames @ 48 kHz mono float32; `rnnoise_process_frame()` also returns a VAD speech probability ([rnnoise.h](https://github.com/xiph/rnnoise/blob/main/include/rnnoise.h)) | Full APM: NS + AGC + AEC + VAD, 10 ms frames, BSD license ([audio_processing.h](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/audio_processing/include/audio_processing.h)) | Full-band (48 kHz) deep-filtering NN; real-time path is a Rust binary / LADSPA plugin (Linux-centric); Python path needs PyTorch ([README](https://github.com/Rikorose/DeepFilterNet)) | Hardware AudioEffect, API 16+, `NoiseSuppressor.isAvailable()` must be checked — many devices return false ([docs](https://developer.android.com/reference/android/media/audiofx/NoiseSuppressor)) |
| Noise-reduction quality | Good for speech; conservative, preserves voice | Good; NS levels 0–3 selectable | State-of-the-art in papers, but heavier | Varies wildly by OEM; often absent |
| Speech preservation | Very natural (designed for voice) | Good | Excellent in demos, can sound processed | Unpredictable |
| CPU (typical) | Very low (~1–3% of one core on modern x86) **[to be measured by us]** | Low–moderate | High vs RNNoise (NN over full band) | Offloaded to DSP on supported devices |
| RAM | ~a few hundred KB state | ~1–2 MB | Tens of MB + model file | OEM-dependent |
| Latency | 10 ms frame, no extra lookahead | 10 ms frames | STFT lookahead adds delay (see `--compensate-delay`) | Device-dependent |
| Windows | ✅ pure C, compiles with MSVC; prebuilt Python wheel exists (`pyrnnoise` 0.4.5 ships `py3-none-win_amd64` wheel bundling RNNoise — [PyPI](https://pypi.org/project/pyrnnoise/)) | ⚠️ official build needs full WebRTC toolchain (depot_tools/GN); only stale PyPI wrapper (`webrtc-audio-processing` 0.1.3, 2019, Linux/ARM-only wheels) — not usable on Windows x64. Would require vendoring the APM subset as C++ | ⚠️ framework claims Windows support for the Python path, but that drags in PyTorch (~hundreds of MB); Rust real-time binary is not a library we can embed without work | n/a |
| Android | ✅ compiles with NDK clang (pure C) | ⚠️ same vendoring problem | ❌ PyTorch/Rust too heavy for mid-range phones; not practical | ✅ native, but optional per device |
| Integration complexity | **Low** — single .c file + header | **High** — large source tree, build system | **Medium–high** | Low (Java), but availability unknown |
| License | **BSD-3-Clause** (verified via GitHub API) — very permissive | BSD | Dual MIT/Apache-2.0 (per README) | Apache-2.0 (Android SDK) |
| Offline | ✅ fully local | ✅ fully local | ✅ fully local | ✅ fully local |

**Recommendation: RNNoise as the single shared engine for the MVP.**
It is the only option that is simultaneously lightweight, permissively licensed, trivially portable to both MSVC and NDK, and backed by a ready-made Windows wheel for cross-checking our own build. We will **not** fake an "intensity slider": RNNoise exposes no meaningful suppression-strength parameter, so the UI will offer ON/OFF plus engine selection, not a fake slider.

**Engine strategy: one engine now, an engine interface for later.** The core will expose `IEngine::process_frame(in, out) -> vad_probability`. MVP ships `RnNoiseEngine` and `PassthroughEngine` (for A/B testing and as a safe fallback). WebRTC APM (vendored NS subset) and DeepFilterNet are **roadmap** engines — selectable in the UI only after they are actually integrated and tested, never promised upfront.

---

## 2. Recommended architecture

```
┌────────────────────────────┐        ┌──────────────────────────────────────┐
│  Windows GUI (PySide6)     │        │  Android app (Kotlin + Compose)      │
│  windows/app               │        │  android/app                         │
│  - device pickers          │        │  - AudioRecord (mic capture)         │
│  - meters, status, errors  │        │  - AudioTrack (monitor, OFF default) │
│  - settings persistence    │        │  - permission & routing handling     │
└────────────┬───────────────┘        └───────────────┬──────────────────────┘
             │ ctypes (clearvoice_core.dll)           │ JNI (libclearvoice_core.so)
             ▼                                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  core/  — shared C++ engine "clearvoice_core"                            │
│  - IEngine interface (process_frame: 480 float32 @ 48 kHz -> vad prob)   │
│  - RnNoiseEngine (vendored rnnoise.c, BSD-3-Clause)                      │
│  - PassthroughEngine                                                     │
│  - Resampler (48 kHz <-> device rate, windowed-sinc)                     │
│  - ChannelConverter (stereo -> mono, etc.)                               │
│  - FrameFifo (accumulates arbitrary callback blocks into 480-sample      │
│    frames; lock-free SPSC ring buffer)                                   │
│  - C API exported for ctypes/JNI                                         │
└──────────────────────────────────────────────────────────────────────────┘
             ▲                                        ▲
   Windows audio I/O                        Android audio I/O
   sounddevice/PortAudio                    AudioRecord/AudioTrack
   (mic in  ->  core  ->  VB-CABLE Input)   (mic -> core -> monitor/record)
```

**Data flow (Windows):**
`Physical mic → PortAudio input callback → ring buffer → worker thread: convert to float32 mono → resample to 48 kHz → FrameFifo → RNNoise 480-sample frames → ring buffer → PortAudio output callback → "CABLE Input" (VB-CABLE) → "CABLE Output" appears as a microphone to Discord/Zoom/Meet.`

**Key design decision — never run the engine inside the audio callback.** The PortAudio callback only copies samples into a lock-free ring buffer (no allocation, no GIL-held work). A dedicated worker thread drains the ring, resamples, and runs RNNoise. This keeps the real-time thread safe from Python's GIL and from any processing hiccup, and it decouples arbitrary callback block sizes from RNNoise's fixed 480-sample frames.

**Repository layout** (adapted from the brief — justified changes noted):

```
ClearVoice/
├── core/                    # shared C++ engine (MSVC -> .dll, NDK -> .so)
│   ├── include/clearvoice/  # public C API + C++ headers
│   ├── src/                 # engines, resampler, converters, ring buffer
│   ├── third_party/rnnoise/ # vendored rnnoise (BSD-3-Clause, pinned commit)
│   ├── tests/               # native unit tests
│   └── CMakeLists.txt
├── windows/
│   ├── app/                 # PySide6 GUI (main window, widgets)
│   ├── audio/               # sounddevice streams, worker thread, meters
│   ├── devices/             # device enumeration, VB-CABLE detection
│   ├── engine_binding/      # ctypes wrapper for clearvoice_core.dll
│   ├── tests/               # pytest
│   └── requirements.txt     # pinned versions
├── android/
│   ├── app/                 # Kotlin/Compose UI, AudioRecord/AudioTrack service
│   └── native/              # JNI bridge + CMake for libclearvoice_core.so
├── benchmarks/              # offline eval: SNR/SI-SDR, latency, CPU
├── scripts/                 # setup, build, test runners
├── docs/                    # this file + ARCHITECTURE.md etc.
└── tests/                   # end-to-end / integration tests
```

---

## 3. Exact Windows stack

| Layer | Technology | Version (pin) | Why |
|---|---|---|---|
| Language | Python | 3.13.14 (installed) | matches user's skill level; type hints throughout |
| GUI | PySide6 (Qt for Python) | latest 6.x via pip, pinned in requirements.txt | modern, native look, permissive LGPL; avoids extra frameworks |
| Audio I/O | `sounddevice` 0.5.6 + bundled PortAudio | 0.5.6 (verified on PyPI; MIT; ships win_amd64 wheels with PortAudio inside; supports callback streams, `query_devices()`, `WasapiSettings`) | one dependency covers capture + playback + device enumeration; no ASIO needed for MVP |
| Math | numpy | 2.3.2 (installed) | conversions, meters, benchmarks |
| Native engine binding | ctypes → `clearvoice_core.dll` | built by us with MSVC | identical engine code as Android; testable in C |
| Cross-check | `pyrnnoise` 0.4.5 wheel | used **only** in benchmarks/tests to validate our DLL output matches the reference RNNoise | Apache-2.0, prebuilt win_amd64 wheel verified on PyPI |
| Build (native) | CMake via `pip install cmake` + MSVC Build Tools 2022 | cmake (pip), cl 14.44 | no new system installs needed |
| Virtual mic | VB-CABLE (VB-Audio) | `VBCABLE_Driver_Pack46.zip` (Nov 2026, XP→Win11, admin install + reboot) — [vb-audio.com/Cable](https://vb-audio.com/Cable/) | donationware/free; appears as "CABLE Input" (playback) and "CABLE Output" (recording); works through PortAudio/WASAPI/MME |
| Packaging (later) | PyInstaller | pinned | single .exe |

---

## 4. Exact Android stack

| Layer | Technology | Why |
|---|---|---|
| Language/UI | Kotlin + Jetpack Compose | modern standard |
| Capture | `AudioRecord` with `MediaRecorder.AudioSource.VOICE_COMMUNICATION`, `AudioFormat.ENCODING_PCM_16BIT`; prefer 48 kHz, fall back to device-native rate + core resampler ([docs](https://developer.android.com/reference/android/media/AudioRecord)) | VOICE_COMMUNICATION enables OEM echo/noise pre-processing when available |
| Processing | JNI → same `libclearvoice_core.so` built from `core/` with NDK clang | one engine, consistent behavior |
| Fallback engine | Android `NoiseSuppressor` (`isAvailable()` checked at runtime) + `PassthroughEngine` | per requirement; never assume it exists |
| Monitoring | `AudioTrack` playback, **OFF by default**, requires headset warning (feedback risk) | safety |
| Routing | `AudioManager.getDevices(GET_DEVICES_INPUTS)` for wired/USB mic selection; `AudioDeviceCallback` for plug events; USB via `UsbManager` | wired earphone + USB-C support |
| Build | Gradle (Android Studio or cmdline-tools) + NDK (CMake) | **SDK not yet installed — Phase 4 prerequisite** |

**What is NOT possible on Android (honest limits):** a normal app cannot replace the system microphone for arbitrary third-party apps or cellular calls. That requires a privileged/system app, root, or the app being the call handler (ConnectionService). ClearVoice Android therefore delivers: in-app cleaned monitoring, cleaned audio recording, and (later) optional integration modes. We will **not** claim system-wide virtual mic on Android.

---

## 5. Windows virtual-microphone routing (exact configuration)

1. User installs VB-CABLE once (admin, reboot). Two new endpoints appear: **CABLE Input** (playback) and **CABLE Output** (recording).
2. ClearVoice input device = physical mic (or wired earphone mic).
3. ClearVoice output device = **CABLE Input**. (Selecting a normal speaker does NOT create a virtual mic — the GUI will only offer cable endpoints for "virtual output", and will detect/report if VB-CABLE is missing.)
4. In Discord/Zoom/Meet, set microphone = **CABLE Output**.
5. ClearVoice GUI shows live validation: cable present? cable clock running? levels flowing? Plus a troubleshooting doc.

---

## 6. Latency & performance considerations

- RNNoise frame = `rnnoise_get_frame_size()` samples @ 48 kHz = **480 samples = 10 ms** (we read the value at runtime, never hardcode). No algorithmic lookahead beyond the frame.
- Budget: input buffer (~5–10 ms with WASAPI shared mode) + FrameFifo accumulation (≤10 ms) + RNNoise (10 ms) + output buffer (~5–10 ms) → **expected end-to-end ≈ 30–50 ms, to be measured** with a loopback test (cable out → cable in) using timestamped impulse signals. No number will be published until measured.
- CPU/RAM: RNNoise state is small (`rnnoise_get_size()`); expect single-digit % of one core on a modern laptop — **measured in Phase 5**, not promised now.
- Callback discipline: no allocation, no I/O, no GUI calls, no logging in audio callbacks; errors cross to the UI via a thread-safe event queue.
- Resampler quality matters: naive linear resampling adds aliasing. Core will implement a windowed-sinc resampler with unit tests (impulse/sine THD checks), because cheap earphone mics often run at 16 kHz/44.1 kHz, not 48 kHz.

---

## 7. Testing strategy

- **Unit (C, core):** frame FIFO with arbitrary block sizes, resampler correctness (sine sweep, SNR of resampled vs reference), channel conversion, engine create/destroy, error paths. Run via CTest.
- **Unit (Python, pytest):** ctypes binding, device manager with mocked `sounddevice`, start/stop lifecycle, settings persistence, meter math.
- **Offline audio quality (`benchmarks/`):** synthesize test signals with numpy (speech-like = formant synthesis or a bundled public-domain sample **[UNVERIFIED: sample source TBD]**, fan = lowpassed noise, keyboard = impulse train, babble = summed modulated tones). Metrics implemented in numpy: SNR, SI-SDR, clipping count, and optionally STOI via `py-stoi` if it installs cleanly (PESQ skipped — licensing). All before/after WAVs kept for listening tests. **No benchmark number will be claimed without a run log.**
- **Latency:** impulse loopback through VB-CABLE, cross-correlation to estimate delay.
- **Hardware:** marked UNVERIFIED unless actually run on a physical mic / earphone mic / phone.

---

## 8. Engineering risks

1. PortAudio device format quirks (24-bit, non-48k, stereo) → handled by converters + resampler, tested.
2. Python GIL in audio path → worker-thread design (Section 2).
3. VB-CABLE needs admin install + reboot; absent on fresh machines → detection + instructions in GUI.
4. Windows apps sometimes ignore per-app device choice → docs + troubleshooting.
5. Android NoiseSuppressor absent on many devices → fallback chain, never assumed.
6. Monitoring feedback → off by default + headset warning.
7. pyrnnoise wheel vs our DLL drift → benchmarks compare outputs; core vendors rnnoise at a pinned commit.
8. Resampler artifacts → windowed-sinc + tests, not linear interpolation.

---

## 9. Milestones & complexity estimate

| Phase | Scope | Est. complexity |
|---|---|---|
| 1 | This document + approval | done now |
| 2 | `core/` engine: vendored RNNoise, resampler, converters, FIFO, C API, C tests, build with MSVC+CMake | Medium (2–4 days) |
| 3 | Windows MVP: sounddevice pipeline, worker thread, PySide6 GUI, device pickers, VB-CABLE integration, pytest | Medium–High (1–2 weeks part-time) |
| 4 | Android MVP: SDK/NDK install, AudioRecord service, JNI, Compose UI, fallback engine, APK build | High (1–2 weeks; SDK download is the long pole) |
| 5 | Benchmarks: latency loopback, CPU/RAM, SNR/SI-SDR, listening tests | Medium (3–5 days) |
| 6 | Polish: persistence, error reporting, PyInstaller exe, release APK, full docs | Medium (1 week) |

---

## 10. Licensing summary

- RNNoise: BSD-3-Clause ✅ (vendor with attribution)
- pyrnnoise: Apache-2.0 ✅ (test/benchmark use only)
- sounddevice / PortAudio: MIT ✅ · PySide6: LGPL ✅ (dynamic linking)
- DeepFilterNet: MIT/Apache-2.0 ✅ (roadmap) · WebRTC APM: BSD ✅ (roadmap)
- VB-CABLE: donationware — free to use; redistribution of the driver in our installer needs VB-Audio's permission, so we **link to their installer** instead of bundling it
- ClearVoice itself: propose MIT
