# Contributing to ClearVoice

Thanks for your interest! This project is built to be learned from — every
component is documented in `docs/`.

## How to work on it

1. Read `docs/PHASE1_TECHNICAL_INVESTIGATION.md` (architecture decisions) and
   `docs/ARCHITECTURE.md` (what exists today).
2. Make changes in small, testable steps. Never claim a feature works without
   running it.
3. Run the tests for what you touched:
   ```powershell
   .\build\core\Release\cv_tests.exe                 # C core unit tests (27)
   python -m pytest windows/tests -v                # Windows app tests (25)
   python benchmarks\run_eval.py                    # quality metrics
   python tools\hw_smoke.py 4                       # real mic/speaker smoke
   ```
4. Keep the real-time rules: no allocation/logging/locks in audio callbacks; no
   exceptions across the C/JNI boundary; glitches counted, never hidden.

## Good first issues

- Engine abstraction: add a second engine behind `IEngine` (e.g. vendored
  WebRTC NS subset) and make it selectable in the UI.
- Android: on-device testing per `docs/ANDROID_SETUP.md` checklist.
- Benchmarks: add STOI (pip `py-stoi`) and real recorded samples.
- Windows: WASAPI exclusive-mode low-latency path; device-change auto-recovery.

## Code style

- Python: type hints, no giant files, comments where the *why* matters.
- C++: C++17, RAII, no exceptions across the C API.
- Kotlin: idiomatic, coroutines for UI state.
