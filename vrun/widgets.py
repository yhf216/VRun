# SPDX-License-Identifier: MPL-2.0
import math
from PySide6.QtCore import QEvent, QLocale, QPointF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDoubleValidator, QPainter, QPainterPath, QPen, QPalette
from PySide6.QtWidgets import QComboBox, QLineEdit, QSizePolicy, QWidget


class ChoiceBox(QComboBox):
    """Scrolling must never accidentally change a selected route or distance."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMaxVisibleItems(10)
        self.view().setSpacing(2)
        self.view().installEventFilter(self)
        self.view().viewport().installEventFilter(self)

    def wheelEvent(self, event):
        event.ignore()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel:
            event.accept()
            return True
        return super().eventFilter(watched, event)


class SpeedInput(QLineEdit):
    valueChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        validator = QDoubleValidator(0.1, 15.0, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        validator.setLocale(QLocale.c())
        self.setValidator(validator)
        self.setMaxLength(8)
        self.setTextMargins(0, 0, 40, 0)
        self.unit_color = QColor("#71839c")
        self.textChanged.connect(lambda _: self.valueChanged.emit(self.value()))

    def value(self):
        try:
            return float(self.text())
        except ValueError:
            return math.nan

    def setValue(self, value):
        self.setText(f"{value:.2f}")

    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(self.unit_color)
        painter.drawText(self.rect().adjusted(0, 0, -12, 0), Qt.AlignRight | Qt.AlignVCenter, "m/s")


class RoutePreview(QWidget):
    """Draw simulated playback progress, not an inferred live phone GPS position."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.route = None
        self.colors = {}
        self.fraction = 0.0
        self.target_fraction = 0.0
        self.running = False
        self.phase = 0
        self.setMinimumHeight(116)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(220)
        self.animation.valueChanged.connect(self._animate)
        self.pulse = QTimer(self)
        self.pulse.setInterval(50)
        self.pulse.timeout.connect(self._pulse)

    def set_route(self, route):
        self.animation.stop()
        self.route = route
        self.fraction = self.target_fraction = 0.0
        self.update()

    def set_running(self, running):
        self.running = running
        if running:
            self.pulse.start()
        else:
            self.pulse.stop()
            self.animation.stop()
            self.fraction = self.target_fraction
        self.update()

    def set_progress(self, fraction, animate=True):
        fraction = max(0.0, min(1.0, float(fraction)))
        self.animation.stop()
        if fraction < self.target_fraction - 0.01:
            self.fraction = 0.0
        self.target_fraction = fraction
        if animate and self.running:
            self.animation.setStartValue(self.fraction)
            self.animation.setEndValue(fraction)
            self.animation.start()
        else:
            self.fraction = fraction
            self.update()

    def _animate(self, value):
        self.fraction = float(value)
        self.update()

    def _pulse(self):
        self.phase = (self.phase + 1) % 40
        self.update()

    def paintEvent(self, event):
        if not self.colors:
            return
        p = self.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p["field"]))
        painter.drawRoundedRect(self.rect(), 9, 9)
        painter.setPen(QPen(QColor(p["grid"]), 1))
        for x in range(16, self.width(), 26):
            for y in range(14, self.height(), 26):
                painter.drawPoint(x, y)
        if not self.route:
            return
        points = self.route.points
        latitude = sum(point.lat for point in points) / len(points)
        coords = [(point.lng * math.cos(math.radians(latitude)), -point.lat) for point in points]
        min_x, max_x = min(x for x, _ in coords), max(x for x, _ in coords)
        min_y, max_y = min(y for _, y in coords), max(y for _, y in coords)
        scale = max(1e-9, min((self.width()-50)/max(max_x-min_x, 1e-9),
                             (self.height()-40)/max(max_y-min_y, 1e-9)))
        mapped = [QPointF(self.width()/2+(x-(min_x+max_x)/2)*scale,
                         self.height()/2+(y-(min_y+max_y)/2)*scale) for x, y in coords]
        full = QPainterPath(mapped[0])
        for point in mapped[1:]:
            full.lineTo(point)
        painter.setPen(QPen(QColor(p["track"]), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(full)
        travelled = self.route.length_m * self.fraction
        completed = QPainterPath(mapped[0])
        position = mapped[0]
        for start, end, distance in zip(mapped, mapped[1:], self.route.segment_lengths):
            if travelled >= distance:
                completed.lineTo(end)
                position = end
                travelled -= distance
            else:
                ratio = travelled / distance if distance else 0
                position = start + (end-start)*ratio
                completed.lineTo(position)
                break
        painter.setPen(QPen(QColor(p["ink"]), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(completed)
        painter.setPen(QPen(QColor(p["success"]), 2))
        painter.setBrush(QColor(p["surface"]))
        painter.drawEllipse(mapped[0], 4, 4)
        glow = QColor(p["ink"])
        glow.setAlpha(38 if not self.running else 32 + int(20*(1+math.sin(self.phase/40*math.tau))))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(position, 12, 12)
        painter.setPen(QPen(QColor(p["surface"]), 2))
        painter.setBrush(QColor(p["ink"]))
        painter.drawEllipse(position, 6, 6)
