# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import argparse
import ctypes
import logging
import os
import sys
import time

from PySide6.QtCore import QSettings, Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                             QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                             QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import __version__
from .device import DeviceBackend
from .paths import app_dir, data_dir, resource_dir
from .routes import load_route, pace_text
from .worker import ProbeWorker, RunWorker, RestoreWorker

LOG = logging.getLogger(__name__)

STYLE = """
QMainWindow, QWidget#root { background: #f3f7fd; color: #182c49; }
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; color: #263b58; }
QFrame#card { background: white; border: 1px solid #e3ebf6; border-radius: 16px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 32px; font-weight: 800; color: #2463db; }
QLabel#muted { color: #7788a0; font-size: 12px; }
QLabel#section { font-size: 15px; font-weight: 700; color: #213c63; }
QLabel#number { color: #205ed5; font-size: 35px; font-weight: 700; }
QLabel#message { padding: 12px 14px; border: 1px solid #dae7fc; border-radius: 10px; color: #365c92; background: #eaf2ff; }
QComboBox, QDoubleSpinBox { background: #f8faff; border: 1px solid #d7e2f1; border-radius: 9px; padding: 9px 11px; min-height: 23px; font-size: 14px; }
QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #3b7af3; }
QComboBox:disabled, QDoubleSpinBox:disabled { color: #8d9bb1; background: #f1f4f9; }
QComboBox QAbstractItemView { background: white; selection-background-color: #dfebff; selection-color: #17478e; border: 1px solid #d7e2f1; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QPushButton { border-radius: 10px; padding: 11px 21px; min-height: 24px; font-weight: 600; }
QPushButton#start { background: #2868e4; color: white; border: 1px solid #2868e4; }
QPushButton#start:hover { background: #1d57ca; }
QPushButton#stop { background: white; color: #315782; border: 1px solid #cbdaf0; }
QPushButton#stop:hover { background: #eaf2ff; }
QPushButton:disabled { background: #e5ebf5; color: #a1aec1; border: 1px solid #e5ebf5; }
QMenuBar { background: #f3f7fd; }
QMenu { background: white; padding: 5px; }
"""


def label(text="", name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return widget, layout


class RoutePreview(QWidget):
    def __init__(self):
        super().__init__()
        self.route = None
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f7faff"))
        painter.setPen(QPen(QColor("#e8eff9"), 1))
        for x in range(0, self.width(), 28):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 28):
            painter.drawLine(0, y, self.width(), y)
        if not self.route:
            return
        points = self.route.points
        average_lat = sum(p.lat for p in points) / len(points)
        import math
        coords = [(p.lng * math.cos(math.radians(average_lat)), -p.lat) for p in points]
        min_x, max_x = min(x for x, _ in coords), max(x for x, _ in coords)
        min_y, max_y = min(y for _, y in coords), max(y for _, y in coords)
        scale = min((self.width() - 44) / max(max_x - min_x, 1e-9),
                    (self.height() - 30) / max(max_y - min_y, 1e-9))
        mapped = [QPointF(self.width()/2 + (x-(min_x+max_x)/2)*scale,
                         self.height()/2 + (y-(min_y+max_y)/2)*scale) for x, y in coords]
        path = QPainterPath(mapped[0])
        for point in mapped[1:]:
            path.lineTo(point)
        painter.setPen(QPen(QColor("#2868e4"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(QColor("#38bfa2"))
        painter.drawEllipse(mapped[0], 5, 5)


class Window(QMainWindow):
    def __init__(self, backend=None, settings=None, poll=True):
        super().__init__()
        self.backend = backend or DeviceBackend()
        self.settings = settings if settings is not None else QSettings("VRun", "VRun")
        self.worker = None
        self.probe_worker = None
        self.route = None
        self._closing = False
        self._allow_close = False
        self._run_started = None
        self._last_restore_failed = False
        self._last_run_error = None
        self._pending_restore = None
        self._pending_start = False
        self.setWindowTitle(f"VRun · 虚拟跑步  {__version__}")
        self.setWindowIcon(QIcon(str(resource_dir() / "assets" / "vrun.ico")))
        self.resize(960, 850)
        self.setMinimumSize(850, 660)
        self.setStyleSheet(STYLE)
        self._create_ui()
        self._load_routes()
        self.speed.setValue(float(self.settings.value("speed", 3.3)))
        self.target.setCurrentText(str(self.settings.value("target", "2 km")))
        self.remind.setChecked(str(self.settings.value("remind", "true")).lower() == "true")
        self._update_pace()
        self._update_reminder()
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        root.setMinimumHeight(790)
        page = QVBoxLayout(root)
        page.setContentsMargins(28, 18, 28, 24)
        page.setSpacing(16)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand.addWidget(label("VRun", "brand"))
        brand.addWidget(label("iPhone 虚拟跑步与定位模拟", "muted"))
        header.addLayout(brand)
        header.addStretch()
        self.run_state = label("●  未运行")
        self.run_state.setStyleSheet("color: #6c829e; font-weight: 600;")
        header.addWidget(self.run_state)
        page.addLayout(header)

        device_card, device_layout = card()
        row = QHBoxLayout()
        details = QVBoxLayout()
        self.device_name = label("连接你的 iPhone", "section")
        self.device_hint = label("通过 USB 连接手机，解锁并确认“信任此电脑”。", "muted")
        details.addWidget(self.device_name)
        details.addWidget(self.device_hint)
        row.addLayout(details)
        row.addStretch()
        self.connection = label("未连接")
        self.connection.setStyleSheet("color: #8190a6;")
        row.addWidget(self.connection)
        device_layout.addLayout(row)
        page.addWidget(device_card)

        middle = QHBoxLayout()
        middle.setSpacing(16)
        route_card, route_layout = card()
        route_card.setMinimumHeight(310)
        route_layout.addWidget(label("运动路线", "section"))
        self.routes = QComboBox()
        self.routes.setObjectName("routeSelector")
        self.routes.currentIndexChanged.connect(self._select_route)
        route_layout.addWidget(self.routes)
        self.preview = RoutePreview()
        route_layout.addWidget(self.preview, 1)
        self.route_info = label("", "muted")
        route_layout.addWidget(self.route_info)
        middle.addWidget(route_card, 1)

        options_card, options = card()
        options_card.setMinimumHeight(310)
        options.setSpacing(8)
        options.addWidget(label("跑步设置", "section"))
        options.addWidget(label("运动速度"))
        speed_row = QHBoxLayout()
        self.speed = QDoubleSpinBox()
        self.speed.setObjectName("speedInput")
        self.speed.setRange(0.1, 15.0)
        self.speed.setDecimals(2)
        self.speed.setSingleStep(0.1)
        self.speed.setSuffix(" m/s")
        self.speed.valueChanged.connect(self._update_pace)
        speed_row.addWidget(self.speed, 1)
        self.pace = label("", "muted")
        speed_row.addWidget(self.pace)
        options.addLayout(speed_row)
        options.addWidget(label("预期提醒距离"))
        self.target = QComboBox()
        self.target.setObjectName("targetInput")
        self.target.setEditable(True)
        self.target.addItems(["2 km", "3 km"])
        self.target.lineEdit().setMaxLength(20)
        options.addWidget(self.target)
        self.remind = QCheckBox("达到目标后发送 Windows 提醒")
        self.remind.toggled.connect(self._update_reminder)
        options.addWidget(self.remind)
        note = label("也可以直接输入其他公里数。\n达到目标后继续运行，每次运动只提醒一次。", "muted")
        note.setWordWrap(True)
        options.addWidget(note)
        options.addStretch()
        middle.addWidget(options_card, 1)
        page.addLayout(middle, 1)

        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.laps = self._stat(stats, "完成圈数", "0", "圈")
        self.distance = self._stat(stats, "模拟估算距离", "0.00", "公里")
        self.elapsed = self._stat(stats, "运动时间", "00:00", "每完成一圈更新圈数与距离")
        page.addLayout(stats)
        self.message = label("选择路线与速度，点击开始。请在运行期间保持 USB 连接。", "message")
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(42)
        page.addWidget(self.message)
        footer = QHBoxLayout()
        disclaimer = label("距离为模拟估算值，可能与手机应用统计不同。", "muted")
        footer.addWidget(disclaimer, 1)
        self.stop_button = QPushButton("停止并恢复定位")
        self.stop_button.setObjectName("stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        self.start_button = QPushButton("开始")
        self.start_button.setObjectName("start")
        self.start_button.setMinimumWidth(112)
        self.start_button.clicked.connect(self.start)
        footer.addWidget(self.stop_button)
        footer.addWidget(self.start_button)
        page.addLayout(footer)
        about = self.menuBar().addMenu("帮助")
        about.addAction("关于与开源许可", self._about)

    def _stat(self, row, title, value, unit):
        widget, layout = card()
        layout.setSpacing(4)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(label(title, "muted"))
        number = label(value, "number")
        layout.addWidget(number)
        layout.addWidget(label(unit, "muted"))
        row.addWidget(widget, 1)
        return number

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
        self.preview.route = self.route
        self.preview.update()
        self.start_button.setEnabled(self.route is not None and self.worker is None and self._pending_restore is None)

    def _update_pace(self, *_):
        self.pace.setText("约 " + pace_text(self.speed.value()))

    def _update_reminder(self, *_):
        self.target.setEnabled(self.remind.isChecked() and self.worker is None)

    def _connected(self, device):
        self.device_name.setText(device.name)
        self.device_hint.setText(f"iOS {device.version}  ·  请保持 USB 连接")
        self.connection.setText("已连接")
        self.connection.setStyleSheet("color: #149779; font-weight: 600;")

    def _disconnected(self, reason):
        self.connection.setText("未连接")
        self.connection.setStyleSheet("color: #8190a6;")
        self.device_name.setText("连接你的 iPhone")
        self.device_hint.setText(reason)
        self.device_hint.setWordWrap(True)

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
        self._last_restore_failed = False
        self._last_run_error = None
        self.laps.setText("0")
        self.distance.setText("0.00")
        self.elapsed.setText("00:00")
        self._run_started = None
        self._set_controls(True)
        worker = RunWorker(self.backend, self.route, self.speed.value(), target, self)
        self.worker = worker
        worker.ready.connect(self._ready)
        worker.message.connect(self.message.setText)
        worker.lap.connect(self._lap)
        worker.target_reached.connect(self._notify)
        worker.failed.connect(self._failed)
        worker.restored.connect(self._restored)
        worker.finished.connect(self._run_finished)
        self.message.setText("正在准备设备，请保持手机解锁…")
        worker.start()

    def _ready(self, device):
        self._connected(device)
        self._run_started = time.monotonic()
        self.run_state.setText("●  运行中")
        self.run_state.setStyleSheet("color: #2463db; font-weight: 600;")
        self.message.setText("正在运行。每完成一圈更新距离，达到目标后提醒并继续运行。")

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
        self.run_state.setStyleSheet("color: #6c829e; font-weight: 600;")
        self._set_controls(False)
        if self._last_restore_failed:
            QMessageBox.warning(self, "请检查手机定位", self.message.text())
        self._finish_close()

    def _tick(self):
        if self._run_started is not None:
            seconds = max(0, int(time.monotonic() - self._run_started))
            self.elapsed.setText(f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600
                                 else f"{seconds // 60:02d}:{seconds % 60:02d}")

    def _about(self):
        QMessageBox.about(self, "关于 VRun",
            f"VRun {__version__}\nWindows 桌面虚拟跑步工具 · iOS 17 以下\n\n"
            "基于 iOSRealRun/iOSRealRun-cli 修改，保留上游提交历史。\n"
            "应用源码：MPL-2.0；设备工具及其他组件按各自许可证分发。\n"
            "完整许可位于安装目录 LICENSES，应用对应源码位于 SOURCE。\n\n"
            "源码：https://github.com/yhf216/VRun\n"
            "上游：https://github.com/iOSRealRun/iOSRealRun-cli")

    def closeEvent(self, event):
        if self._allow_close:
            self.settings.setValue("speed", self.speed.value())
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
    args = parser.parse_args()
    if args.screenshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VRun.Desktop")
    log_dir = data_dir()
    logging.basicConfig(filename=log_dir / "vrun.log", encoding="utf-8", level=logging.INFO,
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
        settings = QSettings(str(args.screenshot.parent / "preview.ini"), QSettings.IniFormat)
        window = Window(settings=settings, poll=False)
    else:
        window = Window()
    window.show()
    if args.screenshot:
        def capture():
            window.grab().save(str(args.screenshot))
            window.close()
        QTimer.singleShot(400, capture)
    return application.exec()
