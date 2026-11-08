"""ClearVoice main window — dark, minimal audio dashboard."""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from audio.pipeline import AudioPipeline, PipelineStats
from devices.manager import DeviceInfo, has_virtual_cable, inputs, list_devices, outputs, virtual_cable_outputs
from engine_binding.cv_core import CoreLib, CvEngineType
from .widgets import LevelMeter, VadLight

BRAND = "ClearVoice"
TAGLINE = "Your voice. Less noise."
CABLE_HELP_URL = "https://vb-audio.com/Cable/"

DARK_QSS = """
QMainWindow, QWidget { background: #0b1220; color: #e5e7eb;
    font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QComboBox, QPushButton, QCheckBox { background: #111827; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 6px; padding: 6px 10px; }
QComboBox::drop-down { border: none; }
QPushButton:hover { background: #1f2937; }
QPushButton#startBtn { background: #16a34a; border: none; font-weight: bold; }
QPushButton#startBtn:hover { background: #22c55e; }
QPushButton#stopBtn { background: #b91c1c; border: none; font-weight: bold; }
QPushButton#stopBtn:hover { background: #ef4444; }
QLabel#brand { font-size: 22px; font-weight: bold; color: #e5e7eb; }
QLabel#tagline { color: #9ca3af; }
QLabel#banner { background: #422006; color: #fbbf24; border: 1px solid #b45309;
    border-radius: 6px; padding: 8px; }
QLabel#err { color: #f87171; }
QLabel#ok { color: #4ade80; }
QPlainTextEdit { background: #111827; border: 1px solid #374151; border-radius: 6px;
    color: #9ca3af; font-family: Consolas, monospace; font-size: 11px; }
QGroupBox { border: 1px solid #374151; border-radius: 8px; margin-top: 8px; }
QGroupBox::title { color: #9ca3af; }
"""


class MainWindow(QMainWindow):
    def __init__(self, core: CoreLib, pipeline_factory=None, device_lister=list_devices,
                 config_path: Path | None = None):
        super().__init__()
        self.core = core
        self._device_lister = device_lister
        self._pipeline_factory = pipeline_factory or (lambda: AudioPipeline(core))
        self.pipeline: AudioPipeline | None = None
        self._devices: list[DeviceInfo] = []
        if config_path is None:
            config_path = Path(os.environ.get("CLEARVOICE_CONFIG", "")) or (
                Path.home() / ".clearvoice" / "config.json"
            )
        self._config_path = Path(config_path)
        self.setWindowTitle(f"{BRAND} — {TAGLINE}")
        self.setMinimumSize(560, 520)
        self.setStyleSheet(DARK_QSS)
        self._build_ui()
        self.refresh_devices()
        self._load_settings()
        # connect save-signals only AFTER the initial load, so populating the
        # combos doesn't clobber the stored config
        self.input_combo.currentIndexChanged.connect(self._save_settings)
        self.output_combo.currentIndexChanged.connect(self._save_settings)
        self.engine_combo.currentIndexChanged.connect(self._save_settings)
        self.suppress_check.toggled.connect(self._save_settings)
        self._dev_timer = QTimer(self)
        self._dev_timer.timeout.connect(self.refresh_devices)
        self._dev_timer.start(2000)
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._update_ui)
        self._ui_timer.start(100)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        head = QHBoxLayout()
        brand = QLabel(BRAND)
        brand.setObjectName("brand")
        tag = QLabel(TAGLINE)
        tag.setObjectName("tagline")
        head.addWidget(brand)
        head.addWidget(tag)
        head.addStretch()
        self.status_label = QLabel("Stopped")
        self.status_label.setObjectName("ok")
        head.addWidget(self.status_label)
        root.addLayout(head)

        self.banner = QLabel("")
        self.banner.setObjectName("banner")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        root.addWidget(self.banner)

        dev_box = QVBoxLayout()
        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Microphone:"))
        self.input_combo = QComboBox()
        row_in.addWidget(self.input_combo, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        row_in.addWidget(self.refresh_btn)
        dev_box.addLayout(row_in)

        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output:"))
        self.output_combo = QComboBox()
        row_out.addWidget(self.output_combo, 1)
        dev_box.addLayout(row_out)
        root.addLayout(dev_box)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Engine:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem(self.core.engine_type_name(CvEngineType.RNNOISE), CvEngineType.RNNOISE)
        self.engine_combo.addItem(self.core.engine_type_name(CvEngineType.PASSTHROUGH), CvEngineType.PASSTHROUGH)
        ctl.addWidget(self.engine_combo)
        self.suppress_check = QCheckBox("Noise suppression ON")
        self.suppress_check.setChecked(True)
        ctl.addWidget(self.suppress_check)
        ctl.addStretch()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self._on_start_stop)
        ctl.addWidget(self.start_btn)
        root.addLayout(ctl)

        meters = QHBoxLayout()
        self.in_meter = LevelMeter()
        self.out_meter = LevelMeter()
        self.vad_light = VadLight()
        for m, lbl in ((self.in_meter, "Input"), (self.out_meter, "Output")):
            col = QVBoxLayout()
            col.addWidget(m, alignment=Qt.AlignmentFlag.AlignHCenter)
            l = QLabel(lbl)
            l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(l)
            meters.addLayout(col)
        vcol = QVBoxLayout()
        vcol.addWidget(self.vad_light, alignment=Qt.AlignmentFlag.AlignHCenter)
        vl = QLabel("Voice")
        vl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vcol.addWidget(vl)
        meters.addLayout(vcol)
        root.addLayout(meters)

        self.stats_label = QLabel("")
        root.addWidget(self.stats_label)
        self.err_label = QLabel("")
        self.err_label.setObjectName("err")
        self.err_label.setWordWrap(True)
        root.addWidget(self.err_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        root.addWidget(self.log)

    # ------------------------------------------------------------- devices
    def refresh_devices(self) -> None:
        try:
            self._devices = self._device_lister()
        except Exception as e:
            self._log(f"device enumeration failed: {e}")
            return
        prev_in = self.input_combo.currentData()
        prev_out = self.output_combo.currentData()
        self.input_combo.clear()
        for d in inputs(self._devices):
            self.input_combo.addItem(f"{d.name}  ({int(d.default_samplerate)} Hz)", d.index)
        self.output_combo.clear()
        for d in outputs(self._devices):
            tag = "  [virtual mic]" if d.role.name == "CABLE_PLAYBACK" else ""
            self.output_combo.addItem(f"{d.name}{tag}", d.index)
        # restore selection if still present
        for combo, prev in ((self.input_combo, prev_in), (self.output_combo, prev_out)):
            if prev is not None:
                idx = combo.findData(prev)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        # cable banner
        if not has_virtual_cable(self._devices):
            self.banner.setText(
                "No virtual audio cable detected. To use ClearVoice as a microphone in calls, "
                f"install VB-CABLE once (admin + reboot): {CABLE_HELP_URL} — then select its "
                "'CABLE Input' as Output and 'CABLE Output' as the microphone in your call app."
            )
            self.banner.setVisible(True)
        else:
            cables = virtual_cable_outputs(self._devices)
            self.banner.setText(
                f"Virtual cable detected: {cables[0].name}. Call apps should use the matching "
                "'CABLE Output' as their microphone."
            )
            self.banner.setVisible(True)

    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    # ------------------------------------------------------- config persistence
    def _save_settings(self, *args) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                json.dumps(
                    {
                        "input_device": self.input_combo.currentData(),
                        "output_device": self.output_combo.currentData(),
                        "engine": int(self.engine_combo.currentData()) if self.engine_combo.currentData() is not None else 0,
                        "suppression": bool(self.suppress_check.isChecked()),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            self._log(f"could not save settings: {e}")

    def _load_settings(self) -> None:
        try:
            cfg = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for combo, key in ((self.input_combo, "input_device"), (self.output_combo, "output_device")):
            v = cfg.get(key)
            if v is not None:
                idx = combo.findData(v)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        eng = cfg.get("engine")
        if eng is not None:
            idx = self.engine_combo.findData(eng)
            if idx >= 0:
                self.engine_combo.setCurrentIndex(idx)
        if "suppression" in cfg:
            self.suppress_check.setChecked(bool(cfg["suppression"]))

    # ------------------------------------------------------------ start/stop
    def _on_start_stop(self) -> None:
        if self.pipeline is not None and self.pipeline.stats.running:
            self._stop()
            return
        if self.input_combo.count() == 0 or self.output_combo.count() == 0:
            self._show_error("No audio devices available.")
            return
        in_idx = self.input_combo.currentData()
        out_idx = self.output_combo.currentData()
        in_dev = next(d for d in self._devices if d.index == in_idx)
        out_dev = next(d for d in self._devices if d.index == out_idx)
        engine = self.engine_combo.currentData()
        if not self.suppress_check.isChecked():
            engine = CvEngineType.PASSTHROUGH
        try:
            self.pipeline = self._pipeline_factory()
            self.pipeline.start(
                in_device=in_dev.index,
                out_device=out_dev.index,
                in_name=in_dev.name,
                out_name=out_dev.name,
                in_rate=int(in_dev.default_samplerate) or 48000,
                out_rate=int(out_dev.default_samplerate) or 48000,
                in_channels=max(1, in_dev.max_input_channels),
                out_channels=max(1, out_dev.max_output_channels),
                engine=engine,
            )
        except Exception as e:
            self._show_error(f"Failed to start: {e}")
            self._log(f"start failed: {e}")
            self.pipeline = None
            return
        self.start_btn.setText("Stop")
        self.start_btn.setObjectName("stopBtn")
        self.start_btn.setStyleSheet("")
        self.status_label.setText("Running")
        self.status_label.setObjectName("ok")
        self._log(
            f"started: {in_dev.name} ({int(in_dev.default_samplerate)} Hz, {in_dev.max_input_channels} ch) -> "
            f"{out_dev.name}; engine={self.pipeline.stats.engine_name}"
        )

    def _stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
            self._log("stopped")
            self.pipeline = None
        self.start_btn.setText("Start")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setStyleSheet("")
        self.status_label.setText("Stopped")
        self.status_label.setObjectName("ok")
        self.err_label.setText("")

    def _show_error(self, msg: str) -> None:
        self.err_label.setText(msg)
        self.status_label.setText("Error")
        self.status_label.setObjectName("err")
        self._log(msg)

    # ------------------------------------------------------------- UI update
    def _update_ui(self) -> None:
        p = self.pipeline
        if p is None:
            return
        s: PipelineStats = p.stats
        if s.error:
            self._show_error(s.error)
        self.in_meter.set_db(s.in_level_db)
        self.out_meter.set_db(s.out_level_db)
        self.vad_light.set_vad(s.vad)
        self.stats_label.setText(
            f"Engine: {s.engine_name}   |   {s.in_rate} Hz -> {s.out_rate} Hz   |   "
            f"frames: {s.frames_processed}   |   buffer: {s.buffer_delay_ms:.0f} ms   |   "
            f"CPU: {s.cpu_percent:.1f}%   |   glitches in/out: {s.in_overflow}/{s.out_underflow}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop()
        super().closeEvent(event)
