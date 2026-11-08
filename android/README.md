# ClearVoice Android

Kotlin app that captures the microphone with `AudioRecord`, runs the **same
shared native core** (RNNoise) via JNI (`libclearvoice_core.so`, built from
`core/` by `app/src/main/cpp/CMakeLists.txt`), and can optionally monitor the
cleaned signal through `AudioTrack` (off by default — use headphones).

## Honest scope statement

A normal Android app **cannot** replace the system microphone for arbitrary
third-party apps or cellular calls — that requires system/root privileges.
This app therefore provides real-time cleaned audio for in-app
monitoring/recording. If the native engine ever fails to load, it falls back to
the device's hardware `NoiseSuppressor` (checked with `isAvailable()` — it is
absent on many phones), and if that is also missing, to passthrough with a
clear status message.

## Build (needs Android Studio or cmdline-tools + NDK)

```bash
cd android
./gradlew assembleDebug          # debug APK -> app/build/outputs/apk/debug/
```

Requires: JDK 17, Android SDK with `platforms;android-35`, `build-tools;35.0.0`,
NDK (any recent, e.g. 27.x) and CMake 3.22.1 (all installable via
`sdkmanager`; see `docs/ANDROID_SETUP.md`).

Install on a device:

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

Grant the microphone permission on first launch.

## Files

| Path | Purpose |
|---|---|
| `app/src/main/cpp/clearvoice_jni.cpp` | JNI bridge (also host-verified, see `tools/jni_host_test`) |
| `app/src/main/cpp/CMakeLists.txt` | builds `libclearvoice_core.so` from `core/` |
| `app/.../audio/ClearVoiceEngine.kt` | native bindings + create/close |
| `app/.../audio/AudioProcessingService.kt` | foreground service: AudioRecord loop → JNI → optional AudioTrack monitor |
| `app/.../audio/NoiseSuppressorFallback.kt` | hardware-effect fallback with `isAvailable()` check |
| `app/.../audio/DeviceMonitor.kt` | input device list (wired/USB) + hotplug callback |
| `app/src/main/java/com/clearvoice/app/MainActivity.kt` | Compose UI |

## Verification status (2026-11-08)

- **JNI bridge host-verified**: `clearvoice_jni.cpp` compiled with MSVC + JDK
  `jni.h` and driven from a real JVM (`tools/jni_host_test`): create → 20 noise
  blocks → 23 RNNoise frames → output drained, `JNI HOST TEST: OK`.
- **Android native libs built with NDK clang 27.3**: `libclearvoice_core.so`
  for `arm64-v8a` and `x86_64` (`scripts/build_android_so_direct.bat`); ELF64
  AArch64 confirmed via `llvm-readelf`; all 11 `Java_com_clearvoice...` JNI
  exports present via `llvm-nm -D`.
- **Full APK (AGP assembleDebug + device install): UNVERIFIED in this sandbox** —
  the sandbox forbids writing `~/.android`, which AGP requires. SDK (platform
  35, build-tools 35.0.0, cmake 3.22.1, NDK 27.3.13750724, all sha256-verified)
  and Gradle 8.10.2 are installed under `tools/` and the build works up to the
  AGP home-dir check. On a normal machine: `cd android && ./gradlew assembleDebug`
  then `adb install app/build/outputs/apk/debug/app-debug.apk` — see
  `docs/ANDROID_SETUP.md` for the device test checklist.
