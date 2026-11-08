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
$env:PYTHONPATH = "tools\pylibs"          # only needed in this sandbox
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

## Verified on this machine (2026-11-08)

- 25/25 pytest tests pass (`python -m pytest windows/tests`).
- Real-hardware smoke (`python tools/hw_smoke.py 4`): WASAPI mic (48 kHz) →
  pipeline → WASAPI speakers, volume 0. Result: 405 engine frames in 4 s
  (real-time cadence), 0 input overflows, 1024 samples startup underflow only,
  process CPU 9.4%, no errors, VAD 0.000 on room noise, engine RNNoise.
- **UNVERIFIED until VB-CABLE is installed:** end-to-end "CABLE Output as mic in
  Discord/Zoom" routing. The device-detection logic is unit-tested with fake
  device lists; the actual cable test needs the driver installed (admin+reboot).

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
