# SPDX-License-Identifier: MPL-2.0
"""Version-specific adapter to the independent JSON-lines developer-service helper."""
from pathlib import Path
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time

from .device import Cancelled, DeviceError
from .paths import data_dir, resource_dir

LOG = logging.getLogger(__name__)


def helper_command():
    if getattr(sys, "frozen", False):
        executable = resource_dir() / "ios17" / "VRun-iOS17.exe"
        if not executable.is_file():
            raise DeviceError("iOS 17+ 组件缺失，请重新安装 VRun。")
        return [str(executable)]
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "ios17_helper" / "main.py")]


class ModernBackend:
    def __init__(self):
        self.process = None
        self.udid = None
        self.responses = queue.Queue()
        self.sequence = 0
        self.log_file = None

    def _read(self, process, responses):
        try:
            for line in process.stdout:
                try:
                    responses.put(json.loads(line))
                except (ValueError, TypeError):
                    LOG.warning("Ignored non-protocol helper output")
        finally:
            responses.put(None)

    def _receive(self, identifier, timeout, cancel=None, status=None):
        deadline = time.monotonic() + timeout
        while True:
            if cancel and cancel.is_set():
                raise Cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeviceError("iOS 17+ 设备响应超时，请检查手机、USB 和网络连接。")
            try:
                response = self.responses.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            if response is None:
                raise DeviceError("iOS 17+ 连接已中断。请保持同一台手机连接后重试。")
            if not isinstance(response, dict):
                continue
            if response.get("event") == "status":
                if status:
                    status(str(response.get("message", "")))
                continue
            if response.get("id") != identifier:
                continue
            if not response.get("ok"):
                raise DeviceError(str(response.get("error", "iOS 17+ 通信失败。"))[:600])
            return response

    def open(self, device, cancel=None, status=lambda text: None):
        if self.process is not None:
            if self.udid != device.udid:
                raise DeviceError("恢复定位前不能切换到另一台手机。")
            if self.process.poll() is None:
                return
            self.close()
        if cancel and cancel.is_set():
            raise Cancelled()
        self.responses = queue.Queue()
        self.udid = device.udid
        self.log_file = (data_dir() / "ios17-helper.log").open("a", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                [*helper_command(), "--udid", device.udid], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.log_file, text=True, encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            threading.Thread(target=self._read, args=(self.process, self.responses), daemon=True).start()
            self._receive(0, 300, cancel, status)
        except BaseException:
            self.close()
            raise

    def request(self, operation, **values):
        if self.process is None or self.process.poll() is not None:
            raise DeviceError("iOS 17+ 连接已中断，请重新连接同一台手机。")
        self.sequence += 1
        try:
            self.process.stdin.write(json.dumps({"id": self.sequence, "op": operation, **values}) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise DeviceError("iOS 17+ 连接已中断，请检查 USB。") from error
        # Once a coordinate is sent, wait for its bounded acknowledgement before clearing.
        return self._receive(self.sequence, 15)

    def prepare(self, device, cancel, status):
        self.open(device, cancel, status)
        return device

    def set_location(self, device, point, cancel):
        if cancel.is_set():
            raise Cancelled()
        if self.udid != device.udid:
            raise DeviceError("设备标识不匹配，已停止发送定位。")
        self.request("set", lat=point.lat, lng=point.lng)

    def reset(self, device):
        try:
            self.open(device)
            self.request("clear")
        finally:
            self.close()

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            try:
                if process.stdin:
                    process.stdin.close()
                process.wait(timeout=22)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=5)
            finally:
                if process.stdout:
                    process.stdout.close()
        if self.log_file:
            self.log_file.close()
            self.log_file = None
        self.udid = None
