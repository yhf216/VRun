# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import argparse
import ctypes
import logging
import math
import os
import sys
import time

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QProgressBar, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from . import __version__, theme
from .device import Device, DeviceBackend
from .paths import app_dir, data_dir, resource_dir
from .routes import load_route, pace_text
from .widgets import ChoiceBox, RoutePreview, SpeedInput
from .worker import ProbeWorker, RunWorker, RestoreWorker

LOG = logging.getLogger(__name__)


def label(text="", name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    if name:
        widget.setObjectName(name)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(7)
    return widget, layout


class Window(QMainWindow):
    def __init__(self, backend=None, settings=None, poll=True):
        super().__init__()
        self.backend = backend or DeviceBackend()
        self.settings = settings if settings is not None else QSettings("VRun", "VRun")
        self.worker = self.probe_worker = self.route = None
        self._closing = self._allow_close = False
        self._run_started = None
        self._last_restore_failed = False
        self._last_run_error = self._pending_restore = None
        self._pending_start = self._applying_theme = False
        self.palette_colors = {}
        self.setWindowTitle(f"VRun · 虚拟跑步  {__version__}")
        self.setWindowIcon(QIcon(str(resource_dir() / "assets" / "vrun.ico")))
        self.resize(850, 700)
        self.setMinimumSize(760, 600)
        self._create_ui()
        self._load_routes()
        try:
            saved_speed = float(self.settings.value("speed", 3.3))
        except (TypeError, ValueError):
            saved_speed = 3.3
        self.speed.setValue(saved_speed if math.isfinite(saved_speed) and 0.1 <= saved_speed <= 15 else 3.3)
        self.target.setCurrentText(str(self.settings.value("target", "2 km")))
        self.remind.setChecked(str(self.settings.value("remind", "true")).lower() == "true")
        self._update_pace()
        self._update_reminder()
        self.theme_choice.currentIndexChanged.connect(self.apply_theme)
        QApplication.styleHints().colorSchemeChanged.connect(self._system_appearance_changed)
        QApplication.instance().paletteChanged.connect(self._system_appearance_changed)
        self.apply_theme()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self._tick)
        self.clock.start(1000)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(5000)
        self.poll_timer.timeout.connect(self._probe)
        if poll:
            self.poll_timer.start()
            QTimer.singleShot(100, self._probe)

    def _create_ui(self):
        root = QWidget()
        root.setObjectName("root")
        root.setMinimumHeight(640)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        page = QVBoxLayout(root)
        page.setContentsMargins(20, 14, 20, 16)
        page.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(label("VRun", "brand"))
        header.addWidget(label("虚拟跑步", "muted"))
        header.addStretch()
        self.run_state = label("●  未运行", "runState")
        self.run_state.setProperty("active", False)
        header.addWidget(self.run_state)
        header.addSpacing(12)
        self.theme_choice = ChoiceBox()
        self.theme_choice.setObjectName("themeSelector")
        self.theme_choice.setFixedWidth(126)
        self.theme_choice.setToolTip("外观：跟随 Windows 或手动选择明暗主题")
        for name, value in (("跟随系统", "system"), ("浅色", "light"), ("深色", "dark")):
            self.theme_choice.addItem(name, value)
        preference = str(self.settings.value("theme", "system"))
        index = self.theme_choice.findData(preference)
        self.theme_choice.setCurrentIndex(max(0, index))
        header.addWidget(self.theme_choice)
        page.addLayout(header)

        device_card, device_layout = card()
        device_layout.setContentsMargins(14, 9, 14, 9)
        row = QHBoxLayout()
        details = QVBoxLayout()
        details.setSpacing(2)
        self.device_name = label("连接你的 iPhone", "section")
        self.device_hint = label("通过 USB 连接并解锁手机，确认“信任此电脑”。", "muted")
        self.device_hint.setWordWrap(True)
        details.addWidget(self.device_name)
        details.addWidget(self.device_hint)
        row.addLayout(details, 1)
        self.connection = label("未连接", "connection")
        self.connection.setProperty("connected", False)
        row.addWidget(self.connection)
        device_layout.addLayout(row)
        page.addWidget(device_card)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stats_cards = []
        self.laps = self._stat(stats, "完成圈数", "0", "圈")
        self.distance = self._stat(stats, "模拟估算距离", "0.00", "公里")
        self.elapsed = self._stat(stats, "运动时间", "00:00", "")
        page.addLayout(stats)

        middle = QHBoxLayout()
        middle.setSpacing(10)
        self.route_card, route_layout = card()
        self.route_card.setMinimumHeight(256)
        route_header = QHBoxLayout()
        route_header.addWidget(label("运动路线", "section"))
        route_header.addStretch()
        self.lap_progress = label("本圈 0%", "muted")
        route_header.addWidget(self.lap_progress)
        route_layout.addLayout(route_header)
        self.routes = ChoiceBox()
        self.routes.setObjectName("routeSelector")
        self.routes.currentIndexChanged.connect(self._select_route)
        route_layout.addWidget(self.routes)
        self.preview = RoutePreview()
        route_layout.addWidget(self.preview, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("lapProgress")
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        route_layout.addWidget(self.progress_bar)
        self.route_info = label("", "muted")
        route_layout.addWidget(self.route_info)
        middle.addWidget(self.route_card, 1)

        options_card, options = card()
        options_card.setMinimumHeight(256)
        options.setSpacing(6)
        options.addWidget(label("跑步设置", "section"))
        options.addWidget(label("运动速度"))
        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)
        self.speed = SpeedInput()
        self.speed.setObjectName("speedInput")
        self.speed.valueChanged.connect(self._update_pace)
        speed_row.addWidget(self.speed, 1)
        self.pace = label("", "muted")
        speed_row.addWidget(self.pace)
        options.addLayout(speed_row)
        options.addWidget(label("预期提醒距离"))
        self.target = ChoiceBox()
        self.target.setObjectName("targetInput")
        self.target.setEditable(True)
        self.target.addItems(["2 km", "3 km"])
        self.target.lineEdit().setMaxLength(20)
        self.target.lineEdit().setPlaceholderText("例如 2.5 km")
        options.addWidget(self.target)
        self.remind = QCheckBox("达到目标后发送 Windows 提醒")
        self.remind.toggled.connect(self._update_reminder)
        options.addWidget(self.remind)
        options.addWidget(label("支持自定义公里数；达标仅提醒，继续运动。", "muted"))
        options.addStretch()
        middle.addWidget(options_card, 1)
        page.addLayout(middle, 1)

        self.message = label("选择路线与速度，点击开始。运行期间请保持 USB 连接。", "message")
        self.message.setWordWrap(True)
        page.addWidget(self.message)
        footer = QHBoxLayout()
        footer.addWidget(label("停止后会发送恢复正常定位命令。", "muted"), 1)
        self.stop_button = QPushButton("停止并恢复定位")
        self.stop_button.setObjectName("stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        self.start_button = QPushButton("开始")
        self.start_button.setObjectName("start")
        self.start_button.setMinimumWidth(108)
        self.start_button.clicked.connect(self.start)
        footer.addWidget(self.stop_button)
        footer.addWidget(self.start_button)
        page.addLayout(footer)

    def _stat(self, row, title, value, unit):
        widget, layout = card()
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(2)
        layout.addWidget(label(title, "muted"))
        values = QHBoxLayout()
        number = label(value, "number")
        values.addWidget(number)
        values.addWidget(label(unit, "muted"), 0, Qt.AlignBottom)
        values.addStretch()
        layout.addLayout(values)
        self.stats_cards.append(widget)
        row.addWidget(widget, 1)
        return number

    def _system_appearance_changed(self, *_):
        self.apply_theme()

    def apply_theme(self, *_):
        if self._applying_theme:
            return
        self._applying_theme = True
        try:
            mode = self.theme_choice.currentData() or "system"
            self.palette_colors = theme.colors(mode)
            self.setStyleSheet(theme.stylesheet(self.palette_colors))
            self.speed.unit_color = QColor(self.palette_colors["muted"])
            self.speed.update()
            self.preview.colors = self.palette_colors
            self.preview.update()
            self.settings.setValue("theme", mode)
            theme.titlebar(self, self.palette_colors["dark"])
        finally:
            self._applying_theme = False

    def _connected(self, device):
        self.device_name.setText(device.name)
        self.device_hint.setText(f"iOS {device.version}  ·  请保持 USB 连接")
        self.connection.setText("已连接")
        self.connection.setProperty("connected", True)
        self._refresh_style(self.connection)

    def _disconnected(self, reason):
        self.connection.setText("未连接")
        self.connection.setProperty("connected", False)
        self._refresh_style(self.connection)
        self.device_name.setText("连接你的 iPhone")
        self.device_hint.setText(reason)

    @staticmethod
    def _refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _ready(self, device):
        self._connected(device)
        self._run_started = time.monotonic()
        self.run_state.setText("●  运行中")
        self.run_state.setProperty("active", True)
        self._refresh_style(self.run_state)
        self.preview.set_running(True)
        self.message.setText("正在运行。图中显示本圈位置与已走路段，圈数和距离在每圈结束时更新。")

    def _on_progress(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        self.preview.set_progress(fraction)
        self.progress_bar.setValue(round(fraction * 1000))
        prefix = f"第 {int(self.laps.text()) + 1} 圈" if self._run_started is not None else "本圈"
        self.lap_progress.setText(f"{prefix} · {fraction:.0%}")

    def _load_routes(self):
        directory = app_dir() / "routes"
        names = {"HNroute.txt": "海宁操场", "ZJG-west.txt": "紫金港 · 西区", "ZJG-east.txt": "紫金港 · 东区"}
        paths = sorted(directory.glob("*.txt"), key=lambda p: p.name.casefold())
        self.routes.blockSignals(True)
        for path in paths:
            self.routes.addItem(names.get(path.name, path.stem), str(path))
        preferred = str(self.settings.value("route", "ZJG-east.txt"))
        index = next((i for i, p in enumerate(paths) if p.name == preferred), 0)
        self.routes.setCurrentIndex(index if paths else -1)
        self.routes.blockSignals(False)
        self._select_route()

    def _select_route(self, *_):
        self.route = None
        try:
            path = self.routes.currentData()
            if not path:
                raise ValueError("没有找到路线，请在安装目录的 routes 文件夹中添加路线文件。")
            self.route = load_route(Path(path))
            self.route_info.setText(f"{self.route.path.name}    ·    每圈约 {self.route.length_m:.0f} 米")
            self.message.setText("选择路线与速度，点击开始。请在运行期间保持 USB 连接。")
        except (ValueError, OSError, UnicodeError) as error:
            self.message.setText(str(error))
            self.route_info.setText("无法读取路线")
        self.preview.set_route(self.route)
        self._on_progress(0)
        self.start_button.setEnabled(self.route is not None and self.worker is None and self._pending_restore is None)

    def _update_pace(self, *_):
        self.pace.setText("约 " + pace_text(self.speed.value()))

    def _update_reminder(self, *_):
        self.target.setEnabled(self.remind.isChecked() and self.worker is None)

    def _probe(self):
        if self._closing or self._pending_start or self.worker is not None or self.probe_worker is not None:
            return
        worker = ProbeWorker(self.backend, self)
        self.probe_worker = worker
        worker.detected.connect(self._connected)
        worker.unavailable.connect(self._disconnected)
        worker.finished.connect(self._probe_finished)
        worker.start()

    def _probe_finished(self):
        worker = self.probe_worker
        self.probe_worker = None
        if worker:
            worker.deleteLater()
        if self._pending_start and not self._closing:
            self._pending_start = False
            QTimer.singleShot(0, self.start)
        self._finish_close()

    def _target_m(self):
        if not self.remind.isChecked():
            return None
        text = self.target.currentText().strip().lower().replace("公里", "").replace("km", "").strip()
        try:
            value = float(text)
            import math
            if not math.isfinite(value) or not 0 < value <= 1000:
                raise ValueError
        except ValueError as error:
            raise ValueError("请输入大于 0、且不超过 1000 的提醒公里数，例如 2、3 或 2.5。") from error
        return value * 1000

    def start(self):
        if self.worker is not None or self.route is None or self._closing or self._pending_restore is not None:
            return
        try:
            target = self._target_m()
        except ValueError as error:
            self.message.setText(str(error))
            return
        if self.probe_worker is not None:
            self._pending_start = True
            self.start_button.setEnabled(False)
            self.probe_worker.cancel.set()
            self.message.setText("正在连接手机，请稍候…")
            return
        speed = self.speed.value()
        if not math.isfinite(speed) or not 0.1 <= speed <= 15:
            self.message.setText("请输入 0.1 至 15 之间的运动速度（m/s）。")
            return
        self._last_restore_failed = False
        self._last_run_error = None
        self.laps.setText("0")
        self.distance.setText("0.00")
        self.elapsed.setText("00:00")
        self._run_started = None
        self._on_progress(0)
        self._set_controls(True)
        worker = RunWorker(self.backend, self.route, self.speed.value(), target, self)
        self.worker = worker
        worker.ready.connect(self._ready)
        worker.message.connect(self.message.setText)
        worker.progress.connect(self._on_progress)
        worker.lap.connect(self._lap)
        worker.target_reached.connect(self._notify)
        worker.failed.connect(self._failed)
        worker.restored.connect(self._restored)
        worker.finished.connect(self._run_finished)
        self.message.setText("正在准备设备，请保持手机解锁…")
        worker.start()

    def _set_controls(self, running):
        self.start_button.setEnabled(not running and self.route is not None and self._pending_restore is None)
        self.stop_button.setEnabled(running or self._pending_restore is not None)
        self.routes.setEnabled(not running)
        self.speed.setEnabled(not running)
        self.remind.setEnabled(not running)
        self.target.setEnabled(not running and self.remind.isChecked())

    def stop(self):
        if self.worker:
            self.stop_button.setEnabled(False)
            self.message.setText("正在停止，请等待恢复定位完成…")
            self.worker.stop()

        elif self._pending_restore is not None:
            self._last_run_error = None
            self._set_controls(True)
            self.stop_button.setEnabled(False)
            worker = RestoreWorker(self.backend, self._pending_restore, self)
            self.worker = worker
            worker.restored.connect(self._restored)
            worker.finished.connect(self._run_finished)
            self.message.setText("正在重新尝试恢复正常定位…")
            worker.start()

    def _failed(self, text):
        self._last_run_error = text
        self.message.setText(text)

    def _lap(self, laps, distance):
        self.laps.setText(str(laps))
        self.distance.setText(f"{distance / 1000:.2f}")

    def _notify(self, distance):
        self.message.setText(f"已达到目标！模拟估算距离 {distance / 1000:.2f} 公里，将继续运行。")
        try:
            from winotify import Notification
            Notification(app_id="VRun.Desktop", title="VRun · 目标已完成",
                         msg=f"已完成 {self.laps.text()} 圈，模拟估算距离 {distance / 1000:.2f} 公里。运动将继续，请手动停止。",
                         icon=str(resource_dir() / "assets" / "vrun.png")).show()
        except Exception:
            LOG.exception("Windows notification failed")
            self.message.setText(self.message.text() + " 系统通知未能发送，请检查 Windows 通知设置。")

    def _restored(self, success, message):
        self._last_restore_failed = not success
        self._pending_restore = None if success else getattr(self.worker, "device", None)
        # Do not overwrite the original preparation error with a generic "stopped" message.
        if message != "已停止。":
            self.message.setText((self._last_run_error + "\n" if self._last_run_error else "") + message)

    def _run_finished(self):
        self._tick()
        self._run_started = None
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.run_state.setText("●  未运行")
        self.run_state.setProperty("active", False)
        self._refresh_style(self.run_state)
        self.preview.set_running(False)
        self._set_controls(False)
        if self._last_restore_failed:
            QMessageBox.warning(self, "请检查手机定位", self.message.text())
        self._finish_close()

    def _tick(self):
        if self._run_started is not None:
            seconds = max(0, int(time.monotonic() - self._run_started))
            self.elapsed.setText(f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600
                                 else f"{seconds // 60:02d}:{seconds % 60:02d}")

    def closeEvent(self, event):
        if self._allow_close:
            if math.isfinite(self.speed.value()) and 0.1 <= self.speed.value() <= 15:
                self.settings.setValue("speed", self.speed.value())
            self.preview.set_running(False)
            try:
                QApplication.styleHints().colorSchemeChanged.disconnect(self._system_appearance_changed)
                QApplication.instance().paletteChanged.disconnect(self._system_appearance_changed)
            except (RuntimeError, TypeError):
                pass
            self.settings.setValue("target", self.target.currentText())
            self.settings.setValue("remind", "true" if self.remind.isChecked() else "false")
            if self.route:
                self.settings.setValue("route", self.route.path.name)
            event.accept()
            return
        event.ignore()
        self._closing = True
        self._pending_start = False
        self.poll_timer.stop()
        if self.probe_worker:
            self.probe_worker.cancel.set()
        if self.worker:
            self.stop()
        self._finish_close()

    def _finish_close(self):
        if self._closing and self.worker is None and self.probe_worker is None:
            self._allow_close = True
            QTimer.singleShot(0, self.close)



def run():
    parser = argparse.ArgumentParser(description="VRun Windows desktop application")
    parser.add_argument("--screenshot", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--theme", choices=("system", "light", "dark"), help=argparse.SUPPRESS)
    parser.add_argument("--running-preview", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.screenshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VRun.Desktop")
    logging.basicConfig(filename=data_dir() / "vrun.log", encoding="utf-8", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    application = QApplication(sys.argv[:1])
    if args.screenshot:
        for font in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
            path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    application.setFont(QFont("Microsoft YaHei UI", 10))
    application.setApplicationName("VRun")
    application.setApplicationVersion(__version__)
    application.setStyle("Fusion")
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        settings = QSettings(str(args.screenshot.parent / ("preview-" + (args.theme or "system") + ".ini")), QSettings.IniFormat)
        if args.theme:
            settings.setValue("theme", args.theme)
        window = Window(settings=settings, poll=False)
        if args.running_preview:
            window._set_controls(True)
            window._ready(Device("preview", "iPhone X · 运行界面预览", "16.7.16"))
            window._run_started = time.monotonic() - 462
            window._tick()
            window._lap(3, window.route.length_m * 3)
            window._on_progress(0.43)
            window.message.setText("运行界面预览：未连接或控制手机。当前位置与本圈进度会随运动实时更新。")
    else:
        window = Window()
        if args.theme:
            window.theme_choice.setCurrentIndex(window.theme_choice.findData(args.theme))
    window.show()
    if args.screenshot:
        def capture():
            window.grab().save(str(args.screenshot))
            window.close()
        QTimer.singleShot(450, capture)
    return application.exec()
