"""Task 4: output soft-limiter — no wrap-around, bounded output."""
from __future__ import annotations

import time

import numpy as np

from audio.pipeline import AudioPipeline, soft_limit
from engine_binding.cv_core import CoreLib, CvEngineType
from .test_pipeline import FakeStreamFactory, _wait_for


def test_soft_limit_bounds_and_counts():
    x = np.array([2.0, -2.0, 0.5, 0.96, -0.99, 0.0], dtype=np.float32)
    n = soft_limit(x)
    assert n == 4  # 2.0, -2.0, 0.96, -0.99 over 0.95
    assert np.max(np.abs(x)) <= 0.999
    assert x[2] == 0.5 and x[5] == 0.0  # below-threshold untouched
    # monotonicity preserved (no sign flip = no wrap)
    assert x[0] > 0 > x[1]


def test_soft_limit_int16_no_wraparound():
    x = np.array([5.0, -5.0, 1.5], dtype=np.float32)
    soft_limit(x)
    pcm = (x * 32767).astype(np.int16)  # what the device path does
    assert pcm.max() <= 32767 and pcm.min() >= -32768
    assert pcm[0] > 0 > pcm[1]  # no wrap to opposite sign


def test_pipeline_output_never_exceeds_limit(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    p.start(in_device=0, out_device=1, in_name="m", out_name="o",
            in_rate=48000, out_rate=48000, in_channels=1, out_channels=1,
            engine=CvEngineType.PASSTHROUGH, blocksize=512, dtype=np.float32)
    try:
        # over-range float input (float streams can exceed 1.0)
        sig = np.full(48000, 1.5, dtype=np.float32)
        for i in range(0, len(sig), 512):
            factory.input.feed_input(sig[i:i + 512].reshape(-1, 1))
            time.sleep(0.004)
            out = factory.output.pull_output()
            assert np.max(np.abs(out)) <= 0.999 + 1e-6, np.max(np.abs(out))
        assert _wait_for(lambda: p.stats.frames_processed >= 80, 20.0)
        assert p.stats.out_clips > 0
        print(f"\n[limiter] out_clips={p.stats.out_clips}")
    finally:
        p.stop()
