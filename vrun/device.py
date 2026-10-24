# SPDX-License-Identifier: MPL-2.0
"""Bounded native-tool calls. Every operation after discovery targets the same UDID."""
from dataclasses import dataclass
from pathlib import Path
import plistlib
import re
import subprocess
import threading
import time

from .paths import resource_dir
from .routes import Point


class DeviceError(RuntimeError):
    pass


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class Device:
    udid: str
    name: str
    version: str


def friendly_error(text: str) -> str:
    lower = text.lower()
    if "no device" in lower or "not found" in lower or "no idevice" in lower:
        return "未找到 iPhone。请检查 USB 连接、解锁手机，并确认 Apple 驱动已安装。"
    if "passcode" in lower or "password" in lower or "locked" in lower:
        return "请先解锁 iPhone，再点击开始。"
    if "trust" in lower or "pairingdialog" in lower or "userdenied" in lower:
        return "请在 iPhone 上选择“信任此电脑”，完成后再次点击开始。"
    if "developer" in lower:
        return "请检查手机的开发者模式和开发者镜像，然后重试。"
    return "设备通信失败：" + text.strip()[:400]


class DeviceBackend:
    def __init__(self, root: Path | None = None):
        self.root = root or resource_dir()
        self.tools = self.root / "libimobiledevice" / "win"

    def command(self, tool: str, *args: str, timeout: float = 12,
                cancel: threading.Event | None = None) -> str:
        executable = self.tools / (tool + ".exe")
        if not executable.is_file():
            raise DeviceError("设备工具缺失，请重新安装 VRun。")
        if cancel and cancel.is_set():
            raise Cancelled()
        try:
            process = subprocess.Popen([str(executable), *map(str, args)], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as error:
            raise DeviceError("无法启动设备工具，请检查安装文件或安全软件的拦截记录。") from error
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancel and cancel.is_set():
                    raise Cancelled()
                if time.monotonic() > deadline:
                    raise DeviceError("设备响应超时，请检查手机是否解锁及 USB 连接。")
                try:
                    stdout, stderr = process.communicate(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")
        if process.returncode or re.search(r"(?im)^error:", output):
            raise DeviceError(friendly_error((output + "\n" + errors).strip()))
        return output

    def probe(self, cancel: threading.Event | None = None) -> Device:
        output = self.command("ideviceinfo", "-s", "-x", timeout=5, cancel=cancel)
        try:
            data = plistlib.loads(output[output.index("<?xml"):].encode("utf-8"))
            device = Device(data["UniqueDeviceID"], data.get("DeviceName", "iPhone"), data["ProductVersion"])
            major = int(device.version.split(".")[0])
        except (ValueError, KeyError, plistlib.InvalidFileException) as error:
            raise DeviceError("无法读取手机信息，请解锁手机并确认信任此电脑。") from error
        if major >= 17:
            raise DeviceError(f"这台设备使用 iOS {device.version}。VRun 初版仅支持 iOS 17 以下版本。")
        return device

    def _mounted(self, device: Device, cancel: threading.Event) -> bool:
        output = self.command("ideviceimagemounter", "-u", device.udid, "-l", "-x", cancel=cancel)
        try:
            data = plistlib.loads(output[output.index("<?xml"):].encode("utf-8"))
        except (ValueError, plistlib.InvalidFileException) as error:
            raise DeviceError("无法读取开发者镜像状态。") from error
        return bool(data.get("ImageSignature"))

    def prepare(self, cancel: threading.Event, status) -> Device:
        status("正在检查手机，请保持 iPhone 解锁…")
        device = self.probe(cancel)
        self.command("idevicepair", "-u", device.udid, "pair", cancel=cancel)
        if int(device.version.split(".")[0]) >= 16:
            output = self.command("idevicedevmodectl", "-u", device.udid, "list", cancel=cancel)
            if not re.search(r"\benabled\b", output, re.IGNORECASE):
                self.command("idevicedevmodectl", "-u", device.udid, "reveal", cancel=cancel)
                raise DeviceError("请在 iPhone 的“设置 → 隐私与安全性 → 开发者模式”中开启开发者模式，重启并确认后再点击开始。")
        if not self._mounted(device, cancel):
            versions = [device.version, ".".join(device.version.split(".")[:2])]
            directory = next((self.root / "DeveloperDiskImage" / version for version in versions
                              if (self.root / "DeveloperDiskImage" / version / "DeveloperDiskImage.dmg").is_file()
                              and (self.root / "DeveloperDiskImage" / version / "DeveloperDiskImage.dmg.signature").is_file()), None)
            if directory is None:
                raise DeviceError(f"没有适配 iOS {device.version} 的开发者镜像，请在 DeveloperDiskImage 中添加对应版本。")
            status("正在准备开发者镜像，请勿拔出 USB…")
            self.command("ideviceimagemounter", "-u", device.udid,
                         str(directory / "DeveloperDiskImage.dmg"),
                         str(directory / "DeveloperDiskImage.dmg.signature"), timeout=90, cancel=cancel)
            if not self._mounted(device, cancel):
                raise DeviceError("开发者镜像挂载失败，请检查手机状态后重试。")
        return device

    def set_location(self, device: Device, point: Point, cancel: threading.Event):
        self.command("idevicesetlocation", "-u", device.udid, "--", f"{point.lat:.8f}",
                     f"{point.lng:.8f}", timeout=8, cancel=cancel)

    def reset(self, device: Device):
        self.command("idevicesetlocation", "-u", device.udid, "reset", timeout=10)
