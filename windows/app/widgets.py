"""Custom widgets for the ClearVoice dashboard."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget


class LevelMeter(QWidget):
    """Vertical audio level meter, -60..0 dBFS, green->amber->red."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = -120.0
        self.setMinimumSize(26, 120)

    def set_db(self, db: float) -> None:
        self._db = max(-60.0, min(0.0, db))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        frac = (self._db + 60.0) / 60.0
        fill_h = int(frac * (h - 4))
        grad = QLinearGradient(0, h - 2, 0, 2)
        grad.setColorAt(0.0, QColor("#22c55e"))
        grad.setColorAt(0.7, QColor("#eab308"))
        grad.setColorAt(1.0, QColor("#ef4444"))
        p.fillRect(0, 0, w, h, QColor("#111827"))
        p.fillRect(2, h - 2 - fill_h, w - 4, fill_h, grad)
        p.setPen(QColor("#374151"))
        p.drawRect(0, 0, w - 1, h - 1)


class VadLight(QWidget):
    """Small round voice-activity indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vad = -1.0
        self.setMinimumSize(16, 16)

    def set_vad(self, v: float) -> None:
        self._vad = v
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = min(self.width(), self.height()) / 2 - 2
        if self._vad >= 0.5:
            c = QColor("#22c55e")
        elif self._vad >= 0.0:
            c = QColor("#4b5563")
        else:
            c = QColor("#1f2937")
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(self.width() / 2 - r), int(self.height() / 2 - r), int(2 * r), int(2 * r))
