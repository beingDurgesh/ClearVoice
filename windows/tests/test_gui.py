"""GUI tests, offscreen (QT_QPA_PLATFORM=offscreen), with fake devices + fake pipeline."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from audio.pipeline import PipelineStats  # noqa: E402
from devices.manager import DeviceInfo  # noqa: E402
from engine_binding.cv_core import CoreLib  # noqa: E402


def _dev(i, name, chin, chout, rate=48000.0):
    return DeviceInfo(index=i, name=name, max_input_channels=chin, max_output_channels=chout, default_samplerate=rate)


DEVICES_WITH_CABLE = [
    _dev(0, "Microphone (USB)", 1, 0),
    _dev(1, "Speakers (USB)", 0, 2),
    _dev(2, "CABLE Input (VB-Audio Virtual Cable)", 0, 2, 44100.0),
    _dev(3, "CABLE Output (VB-Audio Virtual Cable)", 2, 0, 44100.0),
]
DEVICES_NO_CABLE = [d for d in DEVICES_WITH_CABLE if "CABLE" not in d.name]


class FakePipeline:
    def __init__(self):
        self.stats = PipelineStats()
        self.started_with = None

    def start(self, **kwargs):
        self.started_with = kwargs
        self.stats.running = True
        self.stats.engine_name = "RNNoise"
        self.stats.in_rate = kwargs["in_rate"]
        self.stats.out_rate = kwargs["out_rate"]

    def stop(self):
        self.stats.running = False


def test_window_builds_and_populates(qapp, core: CoreLib):
    win = MainWindow(core, pipeline_factory=FakePipeline, device_lister=lambda: DEVICES_WITH_CABLE)
    assert win.input_combo.count() == 1  # only the physical mic
    assert win.output_combo.count() == 2  # speakers + CABLE Input
    assert "[virtual mic]" in win.output_combo.itemText(1)
    assert not win.banner.isHidden() and "Virtual cable detected" in win.banner.text()
    assert win.engine_combo.count() == 2
    win.close()


def test_banner_when_no_cable(qapp, core: CoreLib):
    win = MainWindow(core, pipeline_factory=FakePipeline, device_lister=lambda: DEVICES_NO_CABLE)
    assert not win.banner.isHidden() and "No virtual audio cable" in win.banner.text()
    assert win.output_combo.count() == 1  # only speakers
    win.close()


def test_start_stop_flow(qapp, core: CoreLib):
    made: list[FakePipeline] = []

    def factory():
        p = FakePipeline()
        made.append(p)
        return p

    win = MainWindow(core, pipeline_factory=factory, device_lister=lambda: DEVICES_WITH_CABLE)
    win._on_start_stop()
    assert made and made[0].started_with is not None
    assert made[0].started_with["in_rate"] == 48000
    assert win.start_btn.text() == "Stop"
    assert win.status_label.text() == "Running"
    win._update_ui()  # must not crash
    win._on_start_stop()  # stop
    assert win.start_btn.text() == "Start"
    assert win.status_label.text() == "Stopped"
    assert not made[0].stats.running
    win.close()


def test_suppression_off_uses_passthrough(qapp, core: CoreLib):
    from engine_binding.cv_core import CvEngineType

    made: list[FakePipeline] = []
    win = MainWindow(core, pipeline_factory=lambda: made.append(FakePipeline()) or made[-1],
                     device_lister=lambda: DEVICES_WITH_CABLE)
    win.suppress_check.setChecked(False)
    win._on_start_stop()
    assert made[0].started_with["engine"] == CvEngineType.PASSTHROUGH
    win._on_start_stop()
    win.close()


def test_settings_persist_across_windows(qapp, core: CoreLib, ws_tmp):
    cfg = ws_tmp / "config.json"
    w1 = MainWindow(core, pipeline_factory=FakePipeline, device_lister=lambda: DEVICES_WITH_CABLE, config_path=cfg)
    w1.output_combo.setCurrentIndex(1)  # CABLE Input
    w1.engine_combo.setCurrentIndex(1)   # passthrough
    w1.suppress_check.setChecked(False)
    w1._save_settings()
    assert cfg.exists()
    w1.close()

    w2 = MainWindow(core, pipeline_factory=FakePipeline, device_lister=lambda: DEVICES_WITH_CABLE, config_path=cfg)
    assert w2.output_combo.currentData() == 2  # restored CABLE Input device index
    assert w2.engine_combo.currentData() == 1    # restored passthrough
    assert w2.suppress_check.isChecked() is False
    w2.close()
