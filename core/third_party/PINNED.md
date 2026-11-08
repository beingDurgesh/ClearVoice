# Vendored third-party: RNNoise

- **Project:** xiph/rnnoise — "Recurrent neural network for audio noise reduction"
- **Upstream:** https://github.com/xiph/rnnoise
- **Pinned commit:** `70f1d256acd4b34a572f999a05c87bf00b67730d` (branch `main`, 2025-02-22, signed commit by Jean-Marc Valin)
- **License:** BSD 3-Clause — see `rnnoise/COPYING` (retained, as required)
- **How vendored:** `scripts/fetch_rnnoise.py` downloads each file from
  `raw.githubusercontent.com` at the pinned SHA and verifies size + git blob SHA-1
  against the GitHub git-tree API. Last verified: 2026-11-07, 33/33 files OK.
- **Build mode:** generic C path (no `RNN_ENABLE_X86_RTCD`), so the same sources
  compile with MSVC (Windows) and NDK clang (Android). SIMD dispatch can be
  enabled later without changing our code.
