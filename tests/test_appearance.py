# SPDX-License-Identifier: MPL-2.0
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPalette, QWheelEvent
import pytest
from vrun import theme
from vrun.device import Device
from tests.test_ui import window


def wheel(widget):
    event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(), QPoint(0, 120),
                        Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
    from PySide6.QtWidgets import QApplication
    QApplication.sendEvent(widget, event)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("accent", ["#000000", "#ffffff", "#ffdd00", "#0078d4"])
def test_system_accent_remains_readable(mode, accent, application):
    palette = theme.colors(mode, accent=accent)
    assert theme.contrast(QColor(palette["ink"]), QColor(palette["surface"])) >= 4.5
    assert theme.contrast(QColor(palette["accent_text"]), QColor(palette["accent"])) >= 4.5


def test_theme_tracks_system_and_manual_choice_persists(window, monkeypatch, application):
    state = {"dark": False, "accent": "#0078d4"}
    monkeypatch.setattr(theme, "system_dark", lambda: state["dark"])
    monkeypatch.setattr(theme, "windows_accent", lambda: QColor(state["accent"]))
    window.theme_choice.setCurrentIndex(window.theme_choice.findData("system"))
    window.apply_theme()
    assert window.palette_colors["dark"] is False
    state["dark"] = True
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.palette_colors["dark"] is True
    state["accent"] = "#008080"
    application.paletteChanged.emit(QPalette())
    assert window.palette_colors["accent"] == "#008080"
    window.theme_choice.setCurrentIndex(window.theme_choice.findData("light"))
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.palette_colors["dark"] is False
    assert window.settings.value("theme") == "light"


def test_wheel_cannot_change_route_speed_or_target(window):
    window.target.setCurrentIndex(1)
    index, speed, target = window.routes.currentIndex(), window.speed.value(), window.target.currentText()
    for widget in (window.routes, window.routes.view().viewport(), window.speed, window.target,
                   window.target.lineEdit(), window.target.view().viewport()):
        widget.setFocus()
        wheel(widget)
    assert window.routes.currentIndex() == index
    assert window.speed.value() == speed
    assert window.target.currentText() == target


def test_compact_window_places_statistics_above_route_and_removes_help(window, application):
    window.show()
    application.processEvents()
    assert window.width() == 850 and window.height() == 700
    assert window.menuWidget() is None
    route_y = window.route_card.mapTo(window, QPoint()).y()
    for item in window.stats_cards:
        assert item.mapTo(window, QPoint()).y() + item.height() <= route_y


def test_running_progress_does_not_inflate_completed_lap_distance(window, application):
    window._ready(Device("preview", "Test iPhone", "16.7.16"))
    window._on_progress(0.5)
    window.preview.animation.setCurrentTime(220)
    assert window.preview.fraction == pytest.approx(0.5)
    assert window.progress_bar.value() == 500
    assert "50%" in window.lap_progress.text()
    assert window.laps.text() == "0"
    assert window.distance.text() == "0.00"
    window._on_progress(0.02)
    assert window.preview.fraction == 0
    window.preview.animation.setCurrentTime(220)
    assert window.preview.fraction == pytest.approx(0.02)
    window._run_finished()
    assert not window.preview.running


def test_incomplete_speed_does_not_start_device_control(window):
    window.speed.setText("")
    window.start()
    assert window.worker is None
    assert "0.1" in window.message.text()
