# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent JSON-lines service. No GUI imports; stdout is reserved for protocol replies.

Inspired by iOSRealRun-cli-17's RSD -> DVT -> LocationSimulation flow.
Uses the pinned pymobiledevice3 API; the desktop app communicates only over pipes.
"""
import argparse
import asyncio
from contextlib import AsyncExitStack, suppress
import ctypes
import json
import logging
import math
import sys

LOG = logging.getLogger("VRun.iOS17")


def emit(**message):
    print(json.dumps(message, ensure_ascii=True), flush=True)


def explain(error):
    name = type(error).__name__
    lower = (name + " " + str(error)).lower()
    if "developer" in lower and ("mode" in lower or "enabled" in lower):
        return "请在 iPhone 的“设置 → 隐私与安全性 → 开发者模式”中开启开发者模式，重启并确认。"
    if "locked" in lower or "password" in lower or "passcode" in lower:
        return "请先解锁 iPhone，再点击开始。"
    if "pairingdialog" in lower or "userdenied" in lower or "notpaired" in lower:
        return "请在 iPhone 上确认“信任此电脑”，完成后再次点击开始。"
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "iOS 17+ 准备或通信超时，请检查 USB、手机解锁状态和下载镜像所需的网络。"
    if isinstance(error, ImportError):
        return "iOS 17+ 依赖缺失，请重新安装完整的 VRun 安装包。"
    return f"iOS 17+ 设备通信失败（{name}）：{str(error)[:350]}"


def early_ios17(version):
    parts = tuple(int(value) for value in version.split(".")[:2])
    return parts < (17, 4)


class Session:
    def __init__(self, udid):
        self.udid = udid
        self.stack = AsyncExitStack()
        self.location = None
        self.location_attempted = False

    async def open(self):
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
        from pymobiledevice3.services.amfi import AmfiService
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
        from pymobiledevice3.services.mobile_image_mounter import auto_mount, PersonalizedImageMounter
        from pymobiledevice3.exceptions import AlreadyMountedError

        emit(event="status", message="正在检查 iOS 17+ 设备与开发者模式…")
        lockdown = await create_using_usbmux(serial=self.udid)
        self.stack.push_async_callback(lockdown.close)
        if lockdown.udid != self.udid:
            raise RuntimeError("设备标识不匹配，已取消连接。")
        version = lockdown.product_version
        if int(version.split(".")[0]) < 17:
            raise RuntimeError("此组件仅用于 iOS 17+，旧版设备应使用原有连接方式。")
        if not await lockdown.get_developer_mode_status():
            with suppress(Exception):
                await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
            raise RuntimeError("Developer mode is not enabled")
        if early_ios17(version):
            if sys.platform == "win32" and not ctypes.windll.shell32.IsUserAnAdmin():
                raise RuntimeError("iOS 17.0–17.3 需要管理员权限建立隧道。请停止任务并关闭 VRun，右键选择“以管理员身份运行”。")
            rsd = await self._early_tunnel()
        else:
            emit(event="status", message="正在建立 iOS 17.4+ USB 开发者隧道…")
            rsd = await self.stack.enter_async_context(
                UserspaceRsdTunnel(serial=self.udid, autopair=True, remotepairing_fallback=False))
        if rsd.udid != self.udid:
            raise RuntimeError("开发者隧道连接到了其他设备，已停止。")
        emit(event="status", message="正在检查开发者镜像；首次准备可能需要联网下载，请稍候…")
        async with PersonalizedImageMounter(rsd) as mounter:
            mounted = await mounter.is_image_mounted("Personalized")
        if not mounted:
            with suppress(AlreadyMountedError):
                await auto_mount(rsd)
        provider = await self.stack.enter_async_context(DvtProvider(rsd))
        self.location = await self.stack.enter_async_context(LocationSimulation(provider))

    async def _early_tunnel(self):
        from pymobiledevice3.remote.common import TunnelProtocol
        from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
        from pymobiledevice3.remote.tunnel_service import get_core_device_tunnel_services, start_tunnel

        emit(event="status", message="正在建立 iOS 17.0–17.3 QUIC 隧道，请保持 USB 和 IPv6 网络可用…")
        services = await get_core_device_tunnel_services(udid=self.udid)
        for service in services:
            self.stack.push_async_callback(service.close)
        matching = [service for service in services if service.rsd.udid == self.udid]
        if not matching:
            raise RuntimeError("未发现这台手机的 RemoteXPC 服务。iOS 17.0–17.3 需要 Apple 网络设备驱动、IPv6 和管理员权限；请检查设备管理器及 iTunes/Apple Devices。")
        # The Python >=3.13 default is TCP; early iOS 17 explicitly needs QUIC.
        tunnel = await self.stack.enter_async_context(start_tunnel(matching[0], protocol=TunnelProtocol.QUIC))
        return await self.stack.enter_async_context(RemoteServiceDiscoveryService((tunnel.address, tunnel.port)))

    async def set(self, lat, lng):
        if isinstance(lat, bool) or isinstance(lng, bool):
            raise ValueError("坐标必须是数值。")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            raise ValueError("坐标必须是数值。")
        if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError("坐标超出有效范围。")
        self.location_attempted = True
        await asyncio.wait_for(self.location.set(lat, lng), 8)

    async def clear(self):
        await asyncio.wait_for(self.location.clear(), 8)
        self.location_attempted = False

    async def close(self):
        try:
            if self.location_attempted and self.location is not None:
                await self.clear()
        finally:
            await asyncio.wait_for(self.stack.aclose(), 10)


async def serve(udid):
    session = Session(udid)
    try:
        await asyncio.wait_for(session.open(), 280)
        emit(id=0, ok=True)
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            identifier = None
            try:
                request = json.loads(line)
                identifier = request["id"]
                if request["op"] == "set":
                    await session.set(request["lat"], request["lng"])
                elif request["op"] == "clear":
                    await session.clear()
                else:
                    raise ValueError("未知的定位操作。")
                emit(id=identifier, ok=True)
            except Exception as error:
                LOG.exception("Location operation failed")
                emit(id=identifier, ok=False, error=explain(error))
    except Exception as error:
        LOG.exception("Developer service setup failed")
        emit(id=0, ok=False, error=explain(error))
        return 1
    finally:
        try:
            await session.close()
        except Exception:
            LOG.exception("Developer service cleanup failed")
    return 0


def check_dependencies():
    from importlib.metadata import version
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
    from pymobiledevice3.remote.tunnel_service import get_core_device_tunnel_services, start_tunnel
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
    from pymobiledevice3.services.mobile_image_mounter import auto_mount
    from pytun_pmd3 import TunTapDevice
    import qh3
    import win32security
    emit(ok=True, version=version("pymobiledevice3"), protocol=1)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--udid")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, encoding="utf-8", level=logging.WARNING)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        if args.check:
            return check_dependencies()
        if not args.udid:
            parser.error("--udid is required")
        return asyncio.run(serve(args.udid))
    except Exception as error:
        LOG.exception("iOS 17 helper failed")
        emit(id=0, ok=False, error=explain(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
