# SPDX-License-Identifier: MPL-2.0
import threading
import time

from PySide6.QtCore import QThread, Signal

from .device import Cancelled, DeviceBackend, DeviceError
from .routes import LapCounter, Route


class ProbeWorker(QThread):
    detected = Signal(object)
    unavailable = Signal(str)

    def __init__(self, backend: DeviceBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.cancel = threading.Event()

    def run(self):
        try:
            self.detected.emit(self.backend.probe(self.cancel))
        except Cancelled:
            pass
        except Exception as error:
            self.unavailable.emit(str(error))


class RunWorker(QThread):
    ready = Signal(object)
    message = Signal(str)
    lap = Signal(int, float)
    target_reached = Signal(float)
    failed = Signal(str)
    restored = Signal(bool, str)

    def __init__(self, backend: DeviceBackend, route: Route, speed: float,
                 target_m: float | None, parent=None):
        super().__init__(parent)
        self.backend, self.route, self.speed = backend, route, speed
        self.counter = LapCounter(route.length_m, target_m)
        self.cancel = threading.Event()
        self.device = None

    def stop(self):
        self.cancel.set()

    def run(self):
        device = None
        location_attempted = False
        try:
            device = self.backend.prepare(self.cancel, self.message.emit)
            self.device = device
            if self.cancel.is_set():
                return
            self.ready.emit(device)
            location_attempted = True
            self.backend.set_location(device, self.route.points[0], self.cancel)
            deadline = time.monotonic()
            while not self.cancel.is_set():
                for point, duration in self.route.samples(self.speed):
                    deadline += duration
                    if self.cancel.wait(max(0, deadline - time.monotonic())):
                        raise Cancelled()
                    self.backend.set_location(device, point, self.cancel)
                    # A delayed USB command must not cause a burst of catch-up updates.
                    if time.monotonic() - deadline > duration:
                        deadline = time.monotonic()
                if self.cancel.is_set():
                    break
                notify = self.counter.complete_lap()
                self.lap.emit(self.counter.laps, self.counter.distance_m)
                if notify:
                    self.target_reached.emit(self.counter.distance_m)
        except Cancelled:
            pass
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            if location_attempted and device is not None:
                self.message.emit("正在恢复手机正常定位…")
                try:
                    self.backend.reset(device)
                    self.restored.emit(True, "已停止，并已发送恢复正常定位命令。")
                except Exception as error:
                    self.restored.emit(False, "恢复定位失败：" + str(error) + " 请连接同一台手机后重试。")
            else:
                self.restored.emit(True, "已停止。")


class RestoreWorker(QThread):
    restored = Signal(bool, str)

    def __init__(self, backend, device, parent=None):
        super().__init__(parent)
        self.backend, self.device = backend, device

    def stop(self):
        # Recovery is already bounded by the native-command timeout.
        pass

    def run(self):
        try:
            self.backend.reset(self.device)
            self.restored.emit(True, "已发送恢复正常定位命令。")
        except Exception as error:
            self.restored.emit(False, "恢复定位失败：" + str(error) + " 请检查同一台手机的连接后重试。")
