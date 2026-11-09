# Third-party notices

ClearVoice itself is MIT-licensed. It vendors / depends on:

| Component | Version / source | License | Where |
|---|---|---|---|
| RNNoise (xiph/rnnoise) | commit `70f1d256acd4b34a572f999a05c87bf00b67730d` + model `0a8755f8…` (sha256-verified by `scripts/fetch_rnnoise.py`) | BSD 3-Clause | `core/third_party/rnnoise/` (see its `COPYING`) |
| PySide6 / Qt | 6.12.0 | LGPL v3 (dynamically linked) | Python package |
| sounddevice + PortAudio | sounddevice 0.5.6, PortAudio V19.7.0 (bundled in the win_amd64 wheel) | MIT | Python package |
| numpy | 2.x | BSD-3-Clause | Python package |
| cffi / pycparser | runtime deps of sounddevice | MIT / BSD | Python packages |
| PyInstaller | 6.22.3 | GPL-2.0-with-exception (packaging tool only; not shipped inside the app) | build tool |
| VB-CABLE (VB-Audio Virtual Cable) | **not bundled** — download from https://vb-audio.com/Cable/ | Donationware (free to use); redistribution needs vendor permission | external driver, user-installed |
| Android SDK / NDK / Gradle | SDK 35, NDK 27.3.13750724, Gradle 8.10.2 | Apache-2.0 | build tools |

Model weights note: `rnnoise_data.c` (78 MB) is fetched at build time by
`scripts/fetch_rnnoise.py` with sha256 verification and is intentionally
git-ignored; it remains in early git history (see README note) and is covered by
RNNoise's BSD-3-Clause license either way.
