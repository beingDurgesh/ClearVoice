# Android setup & device testing

## 1. Install the toolchain (one time)

```bash
# cmdline-tools (any recent build), e.g.:
curl -o cmdtools.zip https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip
# extract so that <sdk>/cmdline-tools/latest/bin/sdkmanager.exe exists
# then:
sdkmanager --sdk_root=<sdk> "platform-tools" "platforms;android-35" "build-tools;35.0.0" "cmake;3.22.1" "ndk;27.3.13750724"
# accept licenses:
yes | sdkmanager --sdk_root=<sdk> --licenses
```

Set `ANDROID_HOME`/`ANDROID_SDK_ROOT` to `<sdk>`. JDK 17 required (present on
this machine at `C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot`).

## 2. Build the APK

```bash
cd android
./gradlew assembleDebug        # needs gradle wrapper download on first run
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## 3. Install & test on a phone

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

Test checklist (mark each as verified only when actually done):

- [ ] App launches, asks for RECORD_AUDIO, shows device list (built-in mic,
      wired headset mic, USB-C audio if attached).
- [ ] Start → status shows RUNNING with engine "RNNoise", frames counting up,
      input level moving when you speak.
- [ ] Monitoring ON with headphones: hear yourself cleaned; no feedback squeal.
- [ ] Monitoring OFF (default): no audio out, still processing.
- [ ] Unplug wired headset mid-run → app keeps running on built-in mic or shows a
      clear error (device change handling).
- [ ] Engine = Passthrough → output equals input (A/B).
- [ ] On a device where the native lib is blocked: status shows the
      NoiseSuppressor fallback state (`supported=true/false`).
- [ ] Glitch counters stay 0 during normal use on a mid-range phone; note CPU%.

## 4. What this app deliberately does NOT do

No system-wide virtual microphone (impossible for a normal app), no cellular
call audio path, no cloud upload — all processing is on-device.
