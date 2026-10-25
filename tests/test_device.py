# SPDX-License-Identifier: MPL-2.0
import plistlib
import threading
import pytest
from vrun.device import Device, DeviceBackend, DeviceError, Cancelled
from vrun.routes import Point


def probe_output(version="16.7.16"):
    return plistlib.dumps({"UniqueDeviceID": "test-device", "DeviceName": "Test iPhone",
                           "ProductVersion": version}).decode()


def test_new_ios_is_discovered(monkeypatch):
    backend = DeviceBackend()
    monkeypatch.setattr(backend, "command", lambda *a, **kw: probe_output("17.0"))
    assert backend.probe().version == "17.0"
    assert backend._modern is None


def test_preparation_and_reset_keep_same_device(monkeypatch):
    backend = DeviceBackend()
    commands = []
    def command(tool, *args, **kwargs):
        commands.append((tool, args))
        if tool == "ideviceinfo":
            return probe_output()
        if tool == "idevicedevmodectl":
            return "test-device enabled"
        if tool == "ideviceimagemounter":
            return plistlib.dumps({"ImageSignature": [b"signature"]}).decode()
        return "SUCCESS"
    monkeypatch.setattr(backend, "command", command)
    device = backend.prepare(threading.Event(), lambda text: None)
    backend.set_location(device, Point(30, 120), threading.Event())
    backend.reset(device)
    assert commands[-1] == ("idevicesetlocation", ("-u", "test-device", "reset"))
    for tool, args in commands[1:]:
        assert args[:2] == ("-u", device.udid)


def test_disabled_developer_mode_is_explained(monkeypatch):
    backend = DeviceBackend()
    def command(tool, *args, **kwargs):
        return probe_output() if tool == "ideviceinfo" else "test-device disabled"
    monkeypatch.setattr(backend, "command", command)
    with pytest.raises(DeviceError, match="开发者模式"):
        backend.prepare(threading.Event(), lambda text: None)


def test_cancel_before_native_command_does_not_launch():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        DeviceBackend().command("ideviceinfo", cancel=cancel)
