"""Task 3 tests: drift compensation caps buffer growth; startup vs steady underflow split."""
from __future__ import annotations

import time

import numpy as np

from audio.pipeline import AudioPipeline
from engine_binding.cv_core import CoreLib, CvEngineType
from .test_pipeline import FakeStreamFactory, _wait_for


def _noise(n, seed=9):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * 0.3).astype(np.float32)


def test_drift_compensation_caps_buffer(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    p.set_max_buffer_ms(120.0)  # tight watermark for the test
    p.start(in_device=0, out_device=1, in_name="m", out_name="o",
            in_rate=48000, out_rate=48000, in_channels=1, out_channels=1,
            engine=CvEngineType.RNNOISE, blocksize=512, dtype=np.float32)
    try:
        sig = _noise(48000 * 4)  # 4 s
        # feed paced (worker keeps up) but NEVER pull output -> out ring fills;
        # drift comp must cap it at the watermark
        for i in range(0, len(sig), 512):
            factory.input.feed_input(sig[i:i + 512].reshape(-1, 1))
            time.sleep(0.004)
        assert _wait_for(lambda: p.stats.frames_processed >= 100, 20.0), p.stats.frames_processed
        time.sleep(0.5)
        s = p.stats
        print(f"\n[drift] buffer={s.buffer_delay_ms:.0f} ms (watermark 120) drift_drops={s.drift_drops} overflow={s.out_overflow}")
        assert s.buffer_delay_ms <= 120.0 + 40.0  # capped near watermark (+one block slack)
        assert s.drift_drops > 0  # compensator actually engaged
        assert s.out_overflow == 0  # we never let the ring overflow
    finally:
        p.stop()


def test_startup_vs_steady_underflow_split(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    p.start(in_device=0, out_device=1, in_name="m", out_name="o",
            in_rate=48000, out_rate=48000, in_channels=1, out_channels=1,
            engine=CvEngineType.RNNOISE, blocksize=512, dtype=np.float32)
    try:
        # pull immediately after start, before any input has been processed:
        # ring is empty -> read_padded zero-fills -> counted as STARTUP underflow
        for _ in range(3):
            factory.output.pull_output()
        sig = _noise(48000)
        for i in range(0, len(sig), 512):
            factory.input.feed_input(sig[i:i + 512].reshape(-1, 1))
            time.sleep(0.004)
        time.sleep(0.6)  # cross the 0.5 s startup boundary
        for _ in range(40):
            factory.output.pull_output()
            time.sleep(0.01)
        assert _wait_for(lambda: p.stats.frames_processed >= 80, 20.0), p.stats.frames_processed
        time.sleep(0.8)
        s = p.stats
        print(f"\n[split] total_underflow={s.out_underflow} startup={s.startup_underflow} steady={s.steady_underflow}")
        assert s.startup_underflow > 0  # the initial starvation was captured as startup
        assert s.out_underflow == s.startup_underflow + s.steady_underflow
    finally:
        p.stop()
