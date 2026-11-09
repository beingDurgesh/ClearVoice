"""ClearVoice main window — dark, minimal audio dashboard."""
from __future__ import annotations

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
    QSlider,
    QVBoxLayout,
    QWidget,
)

from audio.pipeline import AudioPipeline, PipelineStats
from devices.manager import DeviceInfo, dedupe_devices, has_virtual_cable, inputs, list_devices, outputs, virtual_cable_outputs
from engine_binding.cv_core import CoreLib, CvEngineType
from .config import load_settings, resolve_config_path, save_settings
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
            config_path = resolve_config_path()
        self._config_path = Path(config_path)
        self._settings_error_logged = False
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
        self.suppress_check.toggled.connect(self._on_suppression_toggled)
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
        self.show_all_check = QCheckBox("Advanced: show all host APIs (MME/DirectSound/WDM-KS duplicates)")
        self.show_all_check.setChecked(False)
        self.show_all_check.toggled.connect(self.refresh_devices)
        dev_box.addWidget(self.show_all_check)
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
        self.in_db_label = QLabel("-inf dBFS")
        self.out_db_label = QLabel("-inf dBFS")
        self.vad_label = QLabel("VAD —")
        for m, lbl, db in ((self.in_meter, "Input", self.in_db_label), (self.out_meter, "Output", self.out_db_label)):
            col = QVBoxLayout()
            col.addWidget(m, alignment=Qt.AlignmentFlag.AlignHCenter)
            l = QLabel(lbl)
            l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(l)
            db.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(db)
            meters.addLayout(col)
        vcol = QVBoxLayout()
        vcol.addWidget(self.vad_light, alignment=Qt.AlignmentFlag.AlignHCenter)
        vl = QLabel("Voice")
        vl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vcol.addWidget(vl)
        self.vad_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vcol.addWidget(self.vad_label)
        meters.addLayout(vcol)
        root.addLayout(meters)

        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("Input gain:"))
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 24)  # dB, default 0 = off
        self.gain_slider.setValue(0)
        self.gain_slider.setMaximumWidth(160)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        gain_row.addWidget(self.gain_slider)
        self.gain_label = QLabel("0 dB")
        gain_row.addWidget(self.gain_label)
        gain_row.addStretch()
        root.addLayout(gain_row)
        self.quiet_hint = QLabel("Input is very quiet (peak < -50 dBFS) — RNNoise leaves quiet frames untouched; try +6..+12 dB gain.")
        self.quiet_hint.setObjectName("banner")
        self.quiet_hint.setWordWrap(True)
        self.quiet_hint.setVisible(False)
        root.addWidget(self.quiet_hint)

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
            raw = self._device_lister()
            self._devices = dedupe_devices(raw, show_all=self.show_all_check.isChecked())
            self._raw_device_count = len(raw)
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

    def _on_suppression_toggled(self, on: bool) -> None:
        """Live-apply the suppression toggle while running (hot engine swap)."""
        p = self.pipeline
        if p is None or not p.stats.running:
            return  # applied at next Start
        engine = self.engine_combo.currentData() if on else CvEngineType.PASSTHROUGH
        rc = p.set_engine(CvEngineType(int(engine)))
        name = p.stats.engine_name
        if rc == 0:
            self._log(f"suppression {'ON' if on else 'OFF'} -> engine hot-swapped to {name}")
        else:
            self._show_error(f"engine switch failed (rc={rc})")

    def _on_gain_changed(self, db: int) -> None:
        self.gain_label.setText(f"{db} dB")
        p = self.pipeline
        if p is not None and p.stats.running:
            p.set_input_gain(db)
        self._save_settings()

    # ------------------------------------------------------- config persistence
    def _save_settings(self, *args) -> None:
        data = {
            "input_device": self.input_combo.currentData(),
            "output_device": self.output_combo.currentData(),
            "engine": int(self.engine_combo.currentData()) if self.engine_combo.currentData() is not None else 0,
            "suppression": bool(self.suppress_check.isChecked()),
            "input_gain_db": int(self.gain_slider.value()),
        }
        try:
            save_settings(self._config_path, data)
        except Exception as e:
            if not self._settings_error_logged:  # log once, not on every signal
                self._settings_error_logged = True
                self._log(f"could not save settings to {self._config_path}: {e}")

    def _load_settings(self) -> None:
        cfg = load_settings(self._config_path)
        if not cfg:
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
        if "input_gain_db" in cfg:
            self.gain_slider.setValue(int(cfg["input_gain_db"]))

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
        self.in_db_label.setText(f"{s.in_level_db:.1f} dBFS")
        self.out_db_label.setText(f"{s.out_level_db:.1f} dBFS")
        self.vad_label.setText(f"VAD {s.vad:.2f}" if s.vad >= 0 else "VAD —")
        self.quiet_hint.setVisible(s.running and s.peak_in_db < -50.0)
        self.stats_label.setText(
            f"Engine: {s.engine_name}   |   {s.in_rate} Hz -> {s.out_rate} Hz   |   "
            f"frames: {s.frames_processed}   |   buffer: {s.buffer_delay_ms:.0f} ms   |   "
            f"CPU: {s.cpu_percent:.1f}%   |   glitches in: {s.in_overflow}   out: {s.out_underflow} "
            f"(startup {s.startup_underflow} + steady {s.steady_underflow})   drift-drops: {s.drift_drops}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop()
        super().closeEvent(event)
