# ClearVoice — troubleshooting

## Windows

**"No virtual audio cable detected" banner**
→ Install VB-CABLE once as Administrator and reboot: https://vb-audio.com/Cable/
→ In ClearVoice click **Refresh**, then select `CABLE Input...` as Output.

**Other side still hears noise in calls**
→ In Discord/Zoom/Meet set **Microphone** to `CABLE Output (VB-Audio Virtual Cable)`, not your physical mic.

**No sound at all in the call**
→ The call app's *speaker* is probably also set to the cable. Set speakers back to your normal output device.

**Cable missing after a Windows update** → reinstall the driver pack, reboot, Refresh.

**Glitches counter > 0**
→ Input overflow: worker thread starved (close heavy apps / antivirus scans).
→ Output underflow: output device can't keep up; try another output or a bigger buffer.

**Mic unplugged while running** → red error line appears; press Stop, replug, Start.

**App won't start / DLL missing** → rebuild the core (README) or set `CLEARVOICE_DLL` to the DLL path.

**Antivirus flags the exe** → PyInstaller onefile builds are commonly flagged; the project is MIT-licensed and builds from source — verify with the test commands in CONTRIBUTING.md.

## Android

**App crashes on start** → check `adb logcat`; the JNI lib loads per-ABI
(arm64-v8a etc. in `build/android-so/`).

**NoiseSuppressor fallback shows supported=false** → your phone's OEM didn't implement the effect; that's expected on many devices — the RNNoise engine is the primary path and needs no hardware effect.

**Monitoring squeals** → monitoring is OFF by default for this reason; use headphones.

**App can't be the mic in other apps** → by Android design, normal apps can't; see `android/README.md` scope statement.

## General

- Everything is local: no network needed for noise suppression, no telemetry, no audio upload.
- If a benchmark number in the docs looks surprising, rerun the benchmark — all of them are reproducible scripts.
