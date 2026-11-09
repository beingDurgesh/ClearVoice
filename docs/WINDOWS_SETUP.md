# ClearVoice on Windows — setup & usage

## Requirements

- Windows 11 (x64)
- Python 3.13 with the deps in `windows/requirements.txt`
  (in this repo's sandbox they were fetched hash-verified into `tools/pylibs`;
  on a normal machine: `pip install -r windows/requirements.txt`)
- The native core built: `build/core/Release/clearvoice_core.dll` (see README)
- **VB-CABLE** (one-time, for the virtual microphone): download
  `VBCABLE_Driver_Pack46.zip` from https://vb-audio.com/Cable/ , run the setup
  **as Administrator**, and **reboot**. (Donationware — free to use; we link to
  the installer rather than bundling the driver.)

## Run

```powershell
cd "C:\Users\91862\Downloads\Noise Cancellation"
python scripts\fetch_rnnoise.py            # REQUIRED first: fetches hash-verified RNNoise + model
# build the native core once (see README "Build & test")
$env:PYTHONPATH = "tools\pylibs"          # only needed in the dev sandbox; normal machines use pip
python windows\main.py
```

## Using ClearVoice in calls (exact routing)

1. In ClearVoice: **Microphone** = your physical mic / wired earphone mic.
2. In ClearVoice: **Output** = `CABLE Input (VB-Audio Virtual Cable)` — the
   entries tagged **[virtual mic]**. (A normal speaker does NOT create a virtual
   microphone.)
3. Click **Start**. The status line shows Running; meters show live levels.
4. In Discord / Zoom / Google Meet: **Settings → Voice → Microphone** =
   `CABLE Output (VB-Audio Virtual Cable)`.
5. Keep the call app's **speaker** on your normal output device.

```
your mic → ClearVoice (RNNoise) → CABLE Input ──(driver)──► CABLE Output → call app
```

## Verified so far (real runs)

Dev machine, 2026-11-08/09:
- C core tests 30/30; pytest 41/41; JNI host test OK; exe bundle runs.
- Real-hardware smoke (`python tools/hw_smoke.py 4`): WASAPI mic (48 kHz) →
  pipeline → WASAPI speakers, volume 0 — 405 engine frames in 4 s, 0 input
  overflows, process CPU 9–25%, no errors.
- 60 s drift report on the real mic: buffer 59–103 ms, slope +0.06 ms/s,
  0 under/overflow after startup.
- Live A/B on the real mic (`python tools/live_ab_test.py`): peak ≈ −50 dBFS;
  ON-vs-OFF noise-floor delta ≈ +0.4 dB at 0 gain, +2.5 dB at +12 dB gain —
  expected, because RNNoise leaves frames below its silence energy gate
  untouched (see `docs/ARCHITECTURE.md`).

User's real machine (2026-11-09), **confirmed by the user**: VB-CABLE installed
and detected by the app; mic → ClearVoice → `CABLE Input` → recording from
`CABLE Output` in Sound Recorder works.

**Still UNVERIFIED (need the user):** Discord/Zoom/Meet end-to-end with
`CABLE Output` as the call mic; audible effectiveness of suppression during a
real call; VB-CABLE impulse loopback latency (`python tools/latency_loopback.py`);
Android APK on a physical phone (`docs/ANDROID_SETUP.md` checklist).

## Troubleshooting

- **"No virtual audio cable detected" banner**: install VB-CABLE (above), reboot,
  click Refresh in ClearVoice.
- **Other side still hears noise**: the call app's microphone is not set to
  `CABLE Output` — set it explicitly.
- **No sound at all in the call**: the call app's *speaker* may also be set to
  the cable — set speakers back to your normal output device.
- **Cable disappeared after a Windows update**: reinstall the driver pack.
- **Glitches shown in the status line** (`glitches in/out`): input overflow means
  the worker thread is starved (close heavy apps); output underflow means the
  output device couldn't keep up (try a larger buffer / different output device).
- **Device unplugged while running**: the stream errors are reported in the red
  error line; press Stop, then Start again after reconnecting.
- **Engine dropdown**: RNNoise (neural denoise) or Passthrough (A/B testing;
  also what "Noise suppression OFF" uses). RNNoise has no strength slider — the
  model doesn't expose one, so we don't fake one.

## Privacy

All processing is local: mic → this process → cable. No audio is recorded,
stored, or uploaded. The app requests no permissions beyond using the microphone
device, which Windows itself mediates.
