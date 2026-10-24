# SPDX-License-Identifier: MPL-2.0
import time
import pytest
from PySide6.QtCore import QSettings
from vrun.app import Window
from vrun.device import DeviceError


@pytest.fixture
def window(application, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    widget = Window(settings=settings, poll=False)
    yield widget
    widget.close()
    application.processEvents()


def test_simple_default_screen(window):
    assert window.route.path.name == "ZJG-east.txt"
    assert window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    assert window.pace.text() == "约 5:03 / 公里"
    assert window.run_state.text() == "●  未运行"


def test_custom_reminder_and_disabled_reminder(window):
    window.target.setCurrentText("2.5 km")
    assert window._target_m() == 2500
    window.target.setCurrentText("nan")
    with pytest.raises(ValueError):
        window._target_m()
    window.remind.setChecked(False)
    assert window._target_m() is None


def test_preparation_failure_returns_to_idle(window, application):
    class BrokenBackend:
        def prepare(self, cancel, status):
            raise DeviceError("请先解锁手机")
    window.backend = BrokenBackend()
    window.start()
    deadline = time.monotonic() + 3
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.005)
    assert window.worker is None
    assert window.start_button.isEnabled()
    assert "解锁手机" in window.message.text()
    assert window.laps.text() == "0"


def test_start_during_probe_is_queued_once(window, application):
    import threading
    from vrun.device import Cancelled
    entered = threading.Event()
    prepares = []
    class SlowProbeBackend:
        def probe(self, cancel):
            entered.set()
            cancel.wait(2)
            raise Cancelled()
        def prepare(self, cancel, status):
            prepares.append(True)
            raise DeviceError("prepare reached")
    window.backend = SlowProbeBackend()
    window._probe()
    assert entered.wait(1)
    window.start()
    deadline = time.monotonic() + 3
    while (not prepares or window.worker is not None or window.probe_worker is not None) and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.005)
    assert prepares == [True]
    assert window.worker is None
    assert window.start_button.isEnabled()
