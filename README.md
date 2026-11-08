# ClearVoice

**Your voice. Less noise.**

ClearVoice is an open-source, cross-platform, real-time AI noise suppressor that
makes inexpensive wired earphone microphones sound significantly cleaner during
calls — fully offline, with no audio ever leaving your device.

- **Windows 11:** captures your microphone, denoises it with RNNoise (a recurrent
  neural network), and plays the cleaned signal into a virtual audio cable
  (VB-CABLE), so Discord / Zoom / Google Meet can use it as their microphone.
- **Android:** a Kotlin app that denoises the mic (built-in / wired / USB) in real
  time through the same native engine via JNI, with optional headphone monitoring.

## Features

- Real-time neural noise suppression (RNNoise, vendored + hash-pinned), 20 ms
  algorithmic latency, ~0.5% of one core (measured — see `docs/BENCHMARKS.md`)
- Arbitrary input formats handled: any sample rate, 1–8 channels, int16/int32/float32
  (windowed-sinc resampler, measured 76–88 dB SNR)
- Windows: device pickers, live level meters, VAD indicator, glitch counters,
  CPU/latency stats, engine selection, settings persistence, VB-CABLE detection
- Android: Compose UI, wired/USB mic selection, hotplug handling, foreground
  service, NoiseSuppressor fallback when the native lib can't load
- Lock-free real-time pipeline: audio callbacks only memcpy; DSP runs on a worker
  thread; errors and glitches are counted and shown, never hidden

## Repository layout

```
core/            shared C++ engine (clearvoice_core.dll / libclearvoice_core.so)
  include/       public C API (ctypes + JNI contract)
  src/           engines, resampler, converters, FrameFifo, SPSC ring, processor
  third_party/   vendored RNNoise @ pinned commit (hash-verified) + license
  tests/         27 C unit tests
windows/         Python app: PySide6 GUI + sounddevice pipeline + ctypes binding
  tests/         26 pytest tests
android/         Kotlin app: Compose UI, AudioRecord service, JNI bridge, CMake
benchmarks/      reproducible eval: synthetic signals, SNR/SI-SDR, latency, CPU
scripts/         reproducible dependency fetching / builds (sandbox-friendly)
tools/           hw smoke test, JNI host test, debug probes
docs/            architecture, setup, benchmarks, troubleshooting
```

## Build & test (verified 2026-11-08 on Windows 11 x64)

```powershell
# 1. native core (MSVC Build Tools 2022; CMake ships with it)
$cm = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
& $cm -S core -B build\core -G "Visual Studio 17 2022" -A x64
& $cm --build build\core --config Release
.\build\core\Release\cv_tests.exe                 # 27 tests, 0 failed

# 2. Python deps (normal machine: pip install -r windows\requirements.txt)
#    (this repo was built in a sandbox where pip is blocked; wheels were fetched
#     hash-verified into tools/pylibs — see scripts/fetch_pywheels.py)
$env:PYTHONPATH = "tools\pylibs"
python -m pytest windows\tests -v                  # 26 passed
python tools\hw_smoke.py 4                         # real mic->speaker run: OK

# 3. run the app
python windows\main.py                             # GUI
# or the packaged bundle:
cmd /c scripts\build_windows_exe.bat               # -> build\dist\ClearVoice\ClearVoice.exe
.\build\dist\ClearVoice\ClearVoice.exe --version
```

Android: `cd android && ./gradlew assembleDebug` (needs JDK 17 + Android SDK/NDK —
see `docs/ANDROID_SETUP.md`). Native libs for arm64-v8a/x86_64 were built here with
NDK clang 27.3 (`scripts/build_android_so_direct.bat`).

## Using the virtual microphone (Windows)

Install VB-CABLE once (admin + reboot): https://vb-audio.com/Cable/ → then:
ClearVoice **Microphone** = your earphone mic · ClearVoice **Output** = `CABLE Input` ·
call app **microphone** = `CABLE Output`. Details + troubleshooting:
`docs/WINDOWS_SETUP.md`, `docs/TROUBLESHOOTING.md`.

## Verification summary (all real, reproducible)

| Check | Result |
|---|---|
| C core unit tests | 27/27 passed |
| Windows pytest suite | 26/26 passed |
| JNI bridge driven from a real JVM | OK |
| Android .so (arm64-v8a, x86_64) with NDK clang | built; 11 JNI exports; ELF AArch64 |
| Real-hardware pipeline smoke (WASAPI mic→speakers) | OK (0 input glitches, CPU 9.4%) |
| Benchmarks (SNR/SI-SDR, latency, CPU) | measured — `docs/BENCHMARKS.md` |
| Packaged Windows exe | `build/dist/ClearVoice/` onedir bundle built with PyInstaller |
| VB-CABLE end-to-end in a call app | **UNVERIFIED** (driver needs admin install on your machine) |
| Android APK on a device | **UNVERIFIED** (sandbox blocks AGP's `~/.android` write; instructions ready) |

## Known limitations (honest)

- RNNoise is conservative: it removes steady noise strongly (~20 dB) but leaves
  speech-like babble and very quiet frames untouched, by design. No fake
  "intensity slider" is exposed because the engine doesn't have one.
- Android: a normal app cannot replace the system mic for other apps or cellular
  calls (needs system privileges) — the app provides cleaned audio in-app.
- 50 Hz mains hum mostly passes the engine's high-pass.

## Roadmap

- Second selectable engine (vendored WebRTC APM NS subset) behind `IEngine`
- WASAPI exclusive-mode / low-latency path on Windows
- STOI metric + real recorded samples in benchmarks
- Device-change auto-recovery, release signing, auto-updater

## License

MIT (see `LICENSE`). RNNoise is BSD-3-Clause (vendored with its `COPYING`).
PySide6/Qt is LGPL (dynamically linked). VB-CABLE is not bundled — we link to the
vendor's installer.

## Privacy

No accounts, no telemetry, no audio upload or storage. All processing is local.
