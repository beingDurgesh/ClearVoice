"""Task 2b: prove the suppression toggle actually changes the output, exercising
the GUI checkbox -> pipeline -> processor -> engine path with a REAL pipeline
(fake PortAudio streams, real native engine)."""
from __future__ import annotations

import time

import numpy as np
import pytest

from app.main_window import MainWindow
from audio.pipeline import AudioPipeline
from devices.manager import DeviceInfo
from engine_binding.cv_core import CoreLib, CvEngineType
from .test_pipeline import FakeStreamFactory, _wait_for


def _dev(i, name, chin, chout, rate=48000.0):
    return DeviceInfo(index=i, name=name, max_input_channels=chin, max_output_channels=chout, default_samplerate=rate)


DEVICES = [_dev(0, "Fake Mic", 1, 0), _dev(1, "Fake Out", 0, 1)]


def _fan(n, seed=5):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    b = np.cumsum(w)
    b -= np.linspace(b[0], b[-1], n)
    b /= np.max(np.abs(b)) + 1e-9
    # one-pole lowpass ~400 Hz
    a = np.exp(-2 * np.pi * 400 / 48000)
    y = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc = a * acc + (1 - a) * b[i]
        y[i] = acc
    return (y * 0.5).astype(np.float32)  # loud fan, rms ~0.2


@pytest.fixture
def rig(qapp, core: CoreLib, ws_tmp):
    factory = FakeStreamFactory()
    holder = {}

    def pipeline_factory():
        p = AudioPipeline(core, stream_factory=factory)
        holder["pipeline"] = p
        return p

    win = MainWindow(core, pipeline_factory=pipeline_factory, device_lister=lambda: DEVICES,
                     config_path=ws_tmp / "cfg.json")
    win.engine_combo.setCurrentIndex(0)  # RNNoise
    win.suppress_check.setChecked(True)
    yield win, factory, holder
    win._stop()
    win.close()


def _feed_and_collect(win, factory, signal, n_blocks):
    """Feed n_blocks of signal via the fake input stream, draining outputs."""
    out = []
    block = 512
    for i in range(n_blocks):
        start = i * block
        blk = signal[start:start + block]
        if len(blk) < block:
            blk = np.pad(blk, (0, block - len(blk)))
        factory.input.feed_input(blk.reshape(-1, 1))
        time.sleep(0.004)
        out.append(factory.output.pull_output().copy())
    return np.concatenate(out)


def test_toggle_changes_output_noise_floor(rig):
    win, factory, holder = rig
    core = win.core
    win._on_start_stop()  # start, RNNoise, suppression ON
    p: AudioPipeline = holder["pipeline"]
    assert p.stats.running and p.stats.engine_name == "RNNoise"

    sig = _fan(48000)  # 1 s loud fan
    # phase 1: ON — feed 1 s, settle
    out_on = _feed_and_collect(win, factory, sig, 48000 // 512)
    assert _wait_for(lambda: p.stats.frames_processed >= 80, 10.0)
    on_tail = out_on[-24000:]  # last 0.5 s, settled
    on_rms = float(np.sqrt(np.mean(on_tail.astype(np.float64) ** 2)))

    # toggle OFF while running — the GUI path
    win.suppress_check.setChecked(False)
    time.sleep(0.05)
    assert p.stats.engine_name == "Passthrough", p.stats.engine_name

    # phase 2: OFF — feed the same signal again
    out_off = _feed_and_collect(win, factory, sig, 48000 // 512)
    off_tail = out_off[-24000:]
    off_rms = float(np.sqrt(np.mean(off_tail.astype(np.float64) ** 2)))

    in_rms = float(np.sqrt(np.mean(sig.astype(np.float64) ** 2)))
    print(f"\n[ab] input rms={in_rms:.4f}  ON rms={on_rms:.4f}  OFF rms={off_rms:.4f}  "
          f"noise-floor reduction ON vs OFF = {20*np.log10(off_rms/max(on_rms,1e-9)):.1f} dB")
    assert off_rms > in_rms * 0.4          # passthrough ~ input level
    assert on_rms < off_rms * 0.316        # ON must cut noise floor by >10 dB

    # toggle back ON live
    win.suppress_check.setChecked(True)
    time.sleep(0.05)
    assert p.stats.engine_name == "RNNoise"


def test_input_gain_scales_and_clips_safely(rig):
    win, factory, holder = rig
    win.suppress_check.setChecked(False)  # passthrough for a clean gain measurement
    win._on_start_stop()
    p: AudioPipeline = holder["pipeline"]
    p.set_input_gain(12.0)  # +12 dB = x4
    sig = (np.full(48000, 0.2, dtype=np.float32))  # constant 0.2
    out = _feed_and_collect(win, factory, sig, 48000 // 512)
    tail = out[-24000:]
    assert _wait_for(lambda: p.stats.frames_processed >= 80, 10.0)
    # 0.2 * 4 = 0.8, no clipping
    assert 0.7 < float(np.mean(np.abs(tail))) < 0.9
    # now +24 dB on a loud signal: must clip at 1.0, never wrap
    p.set_input_gain(24.0)
    loud = np.full(48000, 0.9, dtype=np.float32)
    out2 = _feed_and_collect(win, factory, loud, 48000 // 512)
    assert np.max(np.abs(out2)) <= 1.0 + 1e-6
    assert np.isfinite(out2).all()
    # peak tracking for the quiet-mic hint
    assert p.stats.peak_in_db > -1.0  # 0.9 -> ~-0.9 dBFS
