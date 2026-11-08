"""Tests for the ctypes binding against the real built DLL."""
from __future__ import annotations

import numpy as np
import pytest

from engine_binding.cv_core import CoreLib, CvEngineType, CvSampleFormat


def test_dll_loads_and_version(core: CoreLib, dll_path):
    assert dll_path.exists()
    v = core.version()
    assert isinstance(v, str) and v


def test_engine_rnnoise_frame(core: CoreLib):
    h = core.engine_create(CvEngineType.RNNOISE)
    try:
        assert core.engine_frame_size(h) == 480
        assert core.engine_name(h) == "RNNoise"
        rng = np.random.default_rng(1)
        inp = (rng.standard_normal(480) * 0.8).astype(np.float32)
        vad, out = core.engine_process_frame(h, inp)
        assert 0.0 <= vad <= 1.0
        assert out.dtype == np.float32 and out.shape == (480,)
        assert np.isfinite(out).all()
    finally:
        core.engine_destroy(h)


def test_engine_passthrough_identity(core: CoreLib):
    h = core.engine_create(CvEngineType.PASSTHROUGH)
    try:
        rng = np.random.default_rng(2)
        inp = rng.standard_normal(480).astype(np.float32)
        _, out = core.engine_process_frame(h, inp)
        np.testing.assert_array_equal(out, inp)
    finally:
        core.engine_destroy(h)


def test_processor_pipeline_44k_stereo_int16(core: CoreLib):
    p = core.processor_create(CvEngineType.RNNOISE, 44100, 2, 1 << 16)
    try:
        assert core.processor_in_rate(p) == 44100
        assert core.processor_in_channels(p) == 2
        assert core.processor_engine_name(p) == "RNNoise"
        rng = np.random.default_rng(3)
        data = (rng.standard_normal(4410 * 2) * 16000).astype(np.int16)
        rc = core.processor_push(p, data, CvSampleFormat.INT16)
        assert rc == 0
        assert core.processor_frames_processed(p) >= 8
        avail = core.processor_out_available(p)
        assert avail >= 8 * 480
        buf = np.empty(avail, dtype=np.float32)
        got = core.processor_read_out(p, buf)
        assert got == avail
        assert np.isfinite(buf).all()
        vad = core.processor_last_vad(p)
        assert 0.0 <= vad <= 1.0
    finally:
        core.processor_destroy(p)


def test_processor_rejects_bad_args(core: CoreLib):
    with pytest.raises(RuntimeError):
        core.processor_create(CvEngineType.RNNOISE, 0, 1, 1024)
    with pytest.raises(RuntimeError):
        core.processor_create(CvEngineType.RNNOISE, 48000, 99, 1024)


def test_ring_via_binding(core: CoreLib):
    r = core.ring_create(1024)
    try:
        data = np.arange(100, dtype=np.float32) * 0.01
        assert core.ring_write(r, data) == 100
        assert core.ring_readable(r) == 100
        out = np.zeros(100, dtype=np.float32)
        assert core.ring_read(r, out) == 100
        np.testing.assert_allclose(out, data, atol=1e-6)
        # padded read on empty ring -> zeros + underflow counted
        pad = np.full(10, 9.0, dtype=np.float32)
        assert core.ring_read_padded(r, pad) == 0
        assert (pad == 0).all()
        assert core.ring_underflow(r) == 10
    finally:
        core.ring_destroy(r)


def test_resampler_via_binding(core: CoreLib):
    rs = core.resampler_create(44100, 48000)
    try:
        t = np.arange(44100, dtype=np.float32) / 44100.0
        x = (0.5 * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32)
        n, y = core.resampler_process(rs, x, 48000 + 512)
        assert 47900 < n < 48100
        assert np.isfinite(y).all()
    finally:
        core.resampler_destroy(rs)
