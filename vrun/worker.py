# SPDX-License-Identifier: MPL-2.0
import threading
from time import monotonic

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
    progress = Signal(float)
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
            location_attempted = True
            initial_started = monotonic()
            self.backend.set_location(device, self.route.points[0], self.cancel)
            origin = monotonic()
            self.ready.emit(device)
            self.progress.emit(0.0)
            self._play(device, origin, origin - initial_started)
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
            close = getattr(self.backend, "close", None)
            if close:
                close()

    def _play(self, device, origin, initial_latency):
        lap_seconds = self.route.length_m / self.speed
        # Short loops still need intermediate coordinates before returning to the start.
        interval = min(0.25, lap_seconds / 4)
        if initial_latency >= lap_seconds / 4:
            raise DeviceError("当前设备通信速度无法维持设定的跑步速度，请降低速度或使用更长的路线。")
        latency = min(initial_latency, interval)
        next_update = interval
        last_delivery = origin
        while not self.cancel.is_set():
            lap_end = (self.counter.laps + 1) * lap_seconds
            target_time = min(next_update, lap_end)
            if self.cancel.wait(max(0, origin + target_time - latency - monotonic())):
                raise Cancelled()
            sent = monotonic()
            if sent - last_delivery > 2.0:
                raise DeviceError("设备响应过慢，无法维持设定速度，已停止模拟。请检查 USB 连接后重试。")
            # Skip obsolete samples instead of resetting the time origin or replaying a backlog.
            # Estimate arrival time because the native USB command itself can take >250 ms.
            target_time = min(lap_end, max(target_time, sent - origin + latency))
            if lap_end - target_time <= max(interval, latency):
                # Leave time for the endpoint command; do not send a nearly-complete
                # sample that would keep the device busy past the lap deadline.
                target_time = lap_end
                if self.cancel.wait(max(0, origin + lap_end - latency - monotonic())):
                    raise Cancelled()
                sent = monotonic()
            at_end = target_time == lap_end
            lap_moved = self.route.length_m if at_end else (
                target_time - self.counter.laps * lap_seconds) * self.speed
            point = self.route.position_at(lap_moved)
            self.backend.set_location(device, point, self.cancel)
            delivered = monotonic()
            command_seconds = delivered - sent
            if delivered - last_delivery > 2.0 or command_seconds >= lap_seconds / 4:
                raise DeviceError("设备响应过慢，无法维持设定速度，已停止模拟。请检查 USB 连接或降低速度后重试。")
            latency = 0.7 * latency + 0.3 * command_seconds
            last_delivery = delivered
            self.progress.emit(min(1.0, lap_moved / self.route.length_m))
            if at_end:
                # A faster-than-predicted command must not complete a lap ahead of schedule.
                if self.cancel.wait(max(0, origin + lap_end - monotonic())):
                    raise Cancelled()
                notify = self.counter.complete_lap()
                self.lap.emit(self.counter.laps, self.counter.distance_m)
                if notify:
                    self.target_reached.emit(self.counter.distance_m)
            next_update = target_time + interval


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
