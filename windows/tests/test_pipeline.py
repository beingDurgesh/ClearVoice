"""AudioPipeline tests with fake streams — no audio hardware required.

The fake streams let the test invoke the PortAudio callbacks manually, exactly
like the real RT thread would, while the real worker thread + real native core
process the data.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from audio.pipeline import AudioPipeline
from engine_binding.cv_core import CoreLib, CvEngineType


class FakeStream:
    def __init__(self, kind: str, **kwargs):
        self.kind = kind
        self.kwargs = kwargs
        self.callback = kwargs.get("callback")
        self.started = False
        self.closed = False
        self.dtype = np.dtype(kwargs.get("dtype", "float32"))
        self.channels = kwargs.get("channels", 1)
        self.blocksize = kwargs.get("blocksize", 512)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    # --- test helpers simulating the PortAudio RT thread ---
    def feed_input(self, arr: np.ndarray):
        assert self.kind == "input"
        frames = arr.shape[0]
        self.callback(arr, frames, None, None)

    def pull_output(self) -> np.ndarray:
        assert self.kind == "output"
        out = np.zeros((self.blocksize, self.channels), dtype=np.float32)
        self.callback(out, self.blocksize, None, None)
        return out


class FakeStreamFactory:
    def __init__(self):
        self.streams: list[FakeStream] = []

    def __call__(self, kind: str, **kwargs) -> FakeStream:
        s = FakeStream(kind, **kwargs)
        self.streams.append(s)
        return s

    @property
    def input(self) -> FakeStream:
        return next(s for s in self.streams if s.kind == "input")

    @property
    def output(self) -> FakeStream:
        return next(s for s in self.streams if s.kind == "output")


def _wait_for(cond, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_pipeline_end_to_end_48k_mono(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    rng = np.random.default_rng(10)
    p.start(
        in_device=0, out_device=1, in_name="fake mic", out_name="fake out",
        in_rate=48000, out_rate=48000, in_channels=1, out_channels=1,
        engine=CvEngineType.RNNOISE, blocksize=512, dtype=np.float32,
    )
    try:
        assert p.stats.running
        assert p.stats.engine_name == "RNNoise"
        assert factory.input.started and factory.output.started
        # feed 20 blocks of noise (simulated RT input)
        for _ in range(20):
            block = (rng.standard_normal((512, 1)) * 0.5).astype(np.float32)
            factory.input.feed_input(block)
        assert _wait_for(lambda: p.stats.frames_processed >= 15), "worker did not process frames"
        # pull output blocks (simulated RT output)
        out = factory.output.pull_output()
        assert out.shape == (512, 1)
        assert np.isfinite(out).all()
        # after enough input, output should carry signal (RNNoise passes some noise through)
        rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)))
        assert rms > 0.0
        assert p.stats.error is None
        assert p.stats.in_overflow == 0 and p.stats.out_underflow == 0
        assert p.stats.in_rate == 48000 and p.stats.out_rate == 48000
    finally:
        p.stop()
    assert not p.stats.running
    assert factory.input.closed and factory.output.closed


def test_pipeline_44k1_stereo_int16(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    rng = np.random.default_rng(11)
    p.start(
        in_device=0, out_device=1, in_name="fake 44k mic", out_name="fake out",
        in_rate=44100, out_rate=48000, in_channels=2, out_channels=2,
        engine=CvEngineType.PASSTHROUGH, blocksize=512, dtype=np.int16,
    )
    try:
        for _ in range(20):
            block = (rng.standard_normal((512, 2)) * 12000).astype(np.int16)
            factory.input.feed_input(block)
        assert _wait_for(lambda: p.stats.frames_processed >= 15)
        out = factory.output.pull_output()
        assert out.shape == (512, 2)
        assert np.isfinite(out).all()
        # passthrough at same effective rate: output should approximate input
        assert float(np.abs(out).mean()) > 0.0
        assert p.stats.error is None
    finally:
        p.stop()


def test_start_twice_raises(core: CoreLib):
    factory = FakeStreamFactory()
    p = AudioPipeline(core, stream_factory=factory)
    p.start(0, 1, "a", "b", 48000, 48000, 1, 1, CvEngineType.RNNOISE)
    try:
        with pytest.raises(RuntimeError):
            p.start(0, 1, "a", "b", 48000, 48000, 1, 1, CvEngineType.RNNOISE)
    finally:
        p.stop()
    # after stop, start again must work (lifecycle clean)
    p.start(0, 1, "a", "b", 48000, 48000, 1, 1, CvEngineType.RNNOISE)
    p.stop()
    assert not p.stats.running


def test_stop_is_idempotent(core: CoreLib):
    p = AudioPipeline(core, stream_factory=FakeStreamFactory())
    p.stop()  # never started: must not crash
    p.start(0, 1, "a", "b", 48000, 48000, 1, 1, CvEngineType.RNNOISE)
    p.stop()
    p.stop()
    assert not p.stats.running
