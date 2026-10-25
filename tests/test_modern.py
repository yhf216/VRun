# SPDX-License-Identifier: MPL-2.0
import asyncio
import json
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ios17_helper import main as helper
from vrun.device import Cancelled, Device, DeviceBackend, DeviceError
from vrun.modern import ModernBackend
from vrun.routes import Point
from tests.test_device import probe_output

DEVICE = Device("same-device", "Test iPhone", "17.6")


@pytest.mark.parametrize("version", ["17.0", "17.3.1", "17.4", "18.7", "26.0"])
def test_modern_dispatch_never_uses_legacy_mount_or_location(monkeypatch, version):
    backend = DeviceBackend()
    commands, operations = [], []
    def command(tool, *args, **kwargs):
        commands.append(tool)
        assert tool == "ideviceinfo"
        return probe_output(version)
    class Adapter:
        def prepare(self, device, cancel, status):
            operations.append(("prepare", device.udid))
            return device
        def set_location(self, device, point, cancel):
            operations.append(("set", device.udid))
        def reset(self, device):
            operations.append(("clear", device.udid))
        def close(self):
            operations.append(("close",))
    monkeypatch.setattr(backend, "command", command)
    backend._modern = Adapter()
    device = backend.prepare(threading.Event(), lambda _: None)
    backend.set_location(device, Point(30, 120), threading.Event())
    backend.reset(device)
    backend.close()
    assert commands == ["ideviceinfo"]
    assert operations == [("prepare", "test-device"), ("set", "test-device"),
                          ("clear", "test-device"), ("close",)]


def test_legacy_does_not_load_modern_adapter(monkeypatch):
    backend = DeviceBackend()
    monkeypatch.setattr(backend, "_modern_backend", lambda: pytest.fail("legacy loaded modern helper"))
    monkeypatch.setattr(backend, "command", lambda *a, **kw: "")
    device = Device("legacy", "iPhone X", "16.7.16")
    backend.set_location(device, Point(30, 120), threading.Event())
    backend.reset(device)
    backend.close()


def test_helper_transport_round_trip_and_clean_shutdown(monkeypatch, tmp_path):
    script = tmp_path / "fake_helper.py"
    script.write_text(
        'import json,sys\n'
        'print(json.dumps({"id":0,"ok":True}),flush=True)\n'
        'for line in sys.stdin:\n'
        ' r=json.loads(line)\n'
        ' print(json.dumps({"id":r["id"],"ok":True}),flush=True)\n', encoding="utf-8")
    monkeypatch.setattr("vrun.modern.helper_command", lambda: [sys.executable, str(script)])
    monkeypatch.setattr("vrun.modern.data_dir", lambda: tmp_path)
    backend = ModernBackend()
    backend.prepare(DEVICE, threading.Event(), lambda _: None)
    process = backend.process
    backend.set_location(DEVICE, Point(30, 120), threading.Event())
    backend.reset(DEVICE)
    assert process.poll() == 0
    assert backend.process is None
    assert backend.log_file is None


def test_setup_cancel_reaps_helper(monkeypatch, tmp_path):
    script = tmp_path / "fake_helper.py"
    script.write_text("import sys\nfor line in sys.stdin: pass\n", encoding="utf-8")
    monkeypatch.setattr("vrun.modern.helper_command", lambda: [sys.executable, str(script)])
    monkeypatch.setattr("vrun.modern.data_dir", lambda: tmp_path)
    backend = ModernBackend()
    cancel = threading.Event()
    timer = threading.Timer(0.2, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            backend.prepare(DEVICE, cancel, lambda _: None)
    finally:
        timer.join()
        backend.close()
    assert backend.process is None
    assert backend.log_file is None


def test_response_errors_timeout_and_stale_acknowledgement():
    backend = ModernBackend()
    backend.responses.put({"id": 1, "ok": True})
    backend.responses.put({"id": 2, "ok": False, "error": "test failure"})
    with pytest.raises(DeviceError, match="test failure"):
        backend._receive(2, 1)
    with pytest.raises(DeviceError, match="超时"):
        backend._receive(3, 0.01)
    backend.responses.put(None)
    with pytest.raises(DeviceError, match="中断"):
        backend._receive(4, 1)


def test_cancelled_update_sends_nothing_and_mismatched_device_is_rejected():
    backend = ModernBackend()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        backend.set_location(DEVICE, Point(30, 120), cancel)
    with pytest.raises(DeviceError, match="标识"):
        backend.set_location(DEVICE, Point(30, 120), threading.Event())


@pytest.mark.parametrize("version,expected", [("17.0", True), ("17.3.1", True),
                                            ("17.4", False), ("18.0", False), ("26.0", False)])
def test_early_version_boundary(version, expected):
    assert helper.early_ios17(version) is expected


def test_helper_restores_before_closing_tunnel_even_when_set_fails():
    async def scenario():
        session = helper.Session(DEVICE.udid)
        events = []
        class Location:
            async def set(self, *args):
                events.append("set")
                raise OSError("USB failed")
            async def clear(self):
                events.append("clear")
        async def closed():
            events.append("close")
        session.location = Location()
        session.stack.push_async_callback(closed)
        with pytest.raises(OSError):
            await session.set(30, 120)
        await session.close()
        assert events == ["set", "clear", "close"]
    asyncio.run(scenario())


@pytest.mark.parametrize("lat,lng", [(float("nan"), 0), (91, 0), (0, 181), (True, 0), ("30", 120)])
def test_helper_validates_coordinates_before_sending(lat, lng):
    async def scenario():
        session = helper.Session(DEVICE.udid)
        session.location = SimpleNamespace(set=AsyncMock())
        with pytest.raises(ValueError):
            await session.set(lat, lng)
        session.location.set.assert_not_awaited()
        assert not session.location_attempted
    asyncio.run(scenario())


def test_helper_eof_restores_and_closes(monkeypatch):
    events = []
    class Session:
        def __init__(self, udid):
            assert udid == DEVICE.udid
        async def open(self): events.append("open")
        async def set(self, *args): events.append("set")
        async def clear(self): events.append("clear")
        async def close(self): events.append("close")
    import io
    monkeypatch.setattr(helper, "Session", Session)
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"id":1,"op":"set","lat":30,"lng":120}\n'))
    monkeypatch.setattr(helper, "emit", lambda **kwargs: None)
    assert asyncio.run(helper.serve(DEVICE.udid)) == 0
    assert events == ["open", "set", "close"]


def test_worker_closes_modern_tunnel_if_cancelled_after_prepare(application):
    from vrun.worker import RunWorker
    from tests.test_worker import tiny_route
    events = []
    class Backend:
        def prepare(self, cancel, status):
            cancel.set()
            return DEVICE
        def close(self):
            events.append("close")
    RunWorker(Backend(), tiny_route(), 3.3, None).run()
    assert events == ["close"]
