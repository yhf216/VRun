# SPDX-License-Identifier: MPL-2.0
"""Application colors derived from Windows appearance, without changing OS preferences."""
import ctypes
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from .paths import resource_dir

PALETTES = {
    "light": {
        "background": "#f3f6fc", "surface": "#ffffff", "field": "#f6f8fd",
        "border": "#dce5f2", "text": "#233751", "muted": "#71839c",
        "track": "#dbe5f3", "grid": "#eaf0f8", "success": "#16856b",
        "disabled": "#a5b0c1", "disabled_bg": "#edf1f7",
    },
    "dark": {
        "background": "#111723", "surface": "#1b2433", "field": "#141d2b",
        "border": "#304057", "text": "#e7eefb", "muted": "#a1b1c8",
        "track": "#38485e", "grid": "#243347", "success": "#62d4b4",
        "disabled": "#6d7f98", "disabled_bg": "#243043",
    },
}


def system_dark() -> bool:
    scheme = QApplication.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return not bool(winreg.QueryValueEx(key, "AppsUseLightTheme")[0])
        except OSError:
            pass
    return False


def windows_accent() -> QColor:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
                value = winreg.QueryValueEx(key, "AccentColor")[0]
                return QColor(value & 255, (value >> 8) & 255, (value >> 16) & 255)
        except OSError:
            pass
    return QColor("#2868e4")


def luminance(color: QColor) -> float:
    def linear(value):
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    return sum(weight * linear(value) for weight, value in
               zip((0.2126, 0.7152, 0.0722), (color.redF(), color.greenF(), color.blueF())))


def contrast(first: QColor, second: QColor) -> float:
    values = sorted((luminance(first), luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


def colors(mode: str, *, dark=None, accent=None) -> dict:
    use_dark = (system_dark() if dark is None else dark) if mode == "system" else mode == "dark"
    result = dict(PALETTES["dark" if use_dark else "light"])
    accent = QColor(accent) if accent is not None else windows_accent()
    foreground = max((QColor("white"), QColor("#111723")), key=lambda c: contrast(c, accent))
    ink = QColor(accent)
    if use_dark and ink.value() < 10:
        ink = QColor("#444444")
    for _ in range(40):
        if contrast(ink, QColor(result["surface"])) >= 4.5:
            break
        ink = ink.lighter(110) if use_dark else ink.darker(110)
    result.update(accent=accent.name(), accent_text=foreground.name(), ink=ink.name(),
                  hover=(accent.lighter(112) if use_dark else accent.darker(110)).name(),
                  dark=use_dark)
    return result


def stylesheet(palette: dict) -> str:
    p = palette
    arrow = (resource_dir() / "assets" / ("chevron-dark.svg" if p["dark"] else "chevron-light.svg")).as_posix()
    check = (resource_dir() / "assets" / ("check-dark.svg" if p["accent_text"] != "#ffffff" else "check-light.svg")).as_posix()
    return f"""
QMainWindow, QWidget#root, QScrollArea, QDialog {{ background: {p['background']}; }}
QWidget {{ font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 12px; color: {p['text']}; }}
QScrollArea {{ border: none; }}
QFrame#card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QLabel {{ background: transparent; border: none; }}
QLabel#brand {{ font-size: 27px; font-weight: 800; color: {p['ink']}; }}
QLabel#muted {{ color: {p['muted']}; font-size: 11px; }}
QLabel#section {{ font-size: 13px; font-weight: 700; }}
QLabel#number {{ color: {p['ink']}; font-size: 29px; font-weight: 700; }}
QLabel#runState {{ color: {p['muted']}; font-weight: 600; }}
QLabel#runState[active="true"] {{ color: {p['ink']}; }}
QLabel#connection {{ color: {p['muted']}; font-weight: 600; }}
QLabel#connection[connected="true"] {{ color: {p['success']}; }}
QLabel#message {{ padding: 8px 12px; border: 1px solid {p['border']}; border-radius: 9px; background: {p['surface']}; color: {p['muted']}; }}
QComboBox, QLineEdit {{
    background: {p['field']}; border: 1px solid {p['border']}; border-radius: 9px;
    padding: 7px 12px; min-height: 20px; selection-background-color: {p['accent']}; selection-color: {p['accent_text']};
}}
QComboBox {{ padding-right: 34px; }}
QComboBox:hover, QLineEdit:hover {{ border-color: {p['muted']}; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {p['accent']}; }}
QComboBox:disabled, QLineEdit:disabled {{ color: {p['disabled']}; background: {p['disabled_bg']}; }}
QComboBox::drop-down {{ border: none; background: transparent; width: 30px; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
QComboBox QLineEdit {{ background: transparent; border: none; padding: 0; margin: 0; }}
QComboBox QAbstractItemView {{
    background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']};
    padding: 5px; outline: none; selection-background-color: {p['accent']}; selection-color: {p['accent_text']};
}}
QComboBox QAbstractItemView::item {{ min-height: 29px; padding-left: 8px; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {p['border']}; border-radius: 4px; background: {p['field']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: url("{check}"); }}
QPushButton {{ background: {p['field']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 9px; padding: 9px 18px; min-height: 20px; font-weight: 600; }}
QPushButton#start {{ background: {p['accent']}; color: {p['accent_text']}; border: 1px solid {p['accent']}; }}
QPushButton#start:hover {{ background: {p['hover']}; }}
QPushButton#stop {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; }}
QPushButton#stop:hover {{ background: {p['field']}; }}
QPushButton:disabled {{ background: {p['disabled_bg']}; color: {p['disabled']}; border: 1px solid {p['border']}; }}
QProgressBar {{ background: {p['track']}; border: none; border-radius: 3px; height: 5px; }}
QProgressBar::chunk {{ background: {p['ink']}; border-radius: 3px; }}
QScrollBar:vertical {{ background: {p['background']}; width: 8px; border: none; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


def titlebar(window, dark: bool):
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return
    try:
        value = ctypes.c_int(bool(dark))
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(int(window.winId())), attribute,
                    ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except (AttributeError, OSError):
        pass
