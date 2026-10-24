# SPDX-License-Identifier: MPL-2.0
import subprocess
import threading
from unittest.mock import Mock
import pytest
from vrun.device import DeviceBackend, DeviceError, Cancelled


def test_native_timeout_kills_and_reaps_child(monkeypatch):
    process = Mock(returncode=None)
    process.poll.side_effect = [None]
    process.communicate.return_value = (b"", b"")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    with pytest.raises(DeviceError, match="超时"):
        DeviceBackend().command("ideviceinfo", timeout=-1)
    process.kill.assert_called_once()
    process.communicate.assert_called_once()


def test_cancel_during_command_kills_and_reaps_child(monkeypatch):
    event = threading.Event()
    process = Mock(returncode=None)
    def communicate(timeout=None):
        if timeout is not None:
            event.set()
            raise subprocess.TimeoutExpired("device", timeout)
        return b"", b""
    process.communicate.side_effect = communicate
    process.poll.return_value = None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    with pytest.raises(Cancelled):
        DeviceBackend().command("ideviceinfo", cancel=event)
    process.kill.assert_called_once()


def test_error_output_is_not_reported_as_success(monkeypatch):
    process = Mock(returncode=0)
    process.communicate.return_value = (b"ERROR: No device found!", b"")
    process.poll.return_value = 0
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    with pytest.raises(DeviceError, match="iPhone"):
        DeviceBackend().command("ideviceinfo")
