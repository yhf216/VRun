# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import pytest
from vrun.device import Device, DeviceError
from vrun.routes import Point, Route
from vrun.worker import RunWorker
from tests.test_speed import Clock, Cancellation


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr("vrun.worker.monotonic", value.monotonic)
    return value


class FakeBackend:
    def __init__(self, fail_update=False):
        self.events = []
        self.fail_update = fail_update

    def prepare(self, cancel, status):
        return Device("same-device", "Test iPhone", "16.7.16")

    def set_location(self, device, point, cancel):
        self.events.append(("set", device.udid, point))
        if self.fail_update:
            raise DeviceError("USB disconnected")

    def reset(self, device):
        self.events.append(("reset", device.udid))


def tiny_route():
    a, b = Point(30, 120), Point(30.00001, 120)
    return Route(Path("test.txt"), (a, b, a), (0.001, 0.001))


def test_complete_loop_before_counting_and_reset_after_stop(application, clock):
    backend = FakeBackend()
    worker = RunWorker(backend, tiny_route(), 10, 0.002)
    worker.cancel = Cancellation(clock)
    laps, reminders = [], []
    worker.lap.connect(lambda count, distance: (laps.append(count), worker.stop()))
    worker.target_reached.connect(reminders.append)
    worker.run()
    assert laps == [1]
    assert reminders == [0.002]
    assert backend.events[-2] == ("set", "same-device", tiny_route().points[0])
    assert backend.events[-1] == ("reset", "same-device")


def test_failure_still_restores_without_counting_lap(application, clock):
    backend = FakeBackend(fail_update=True)
    worker = RunWorker(backend, tiny_route(), 10, None)
    worker.cancel = Cancellation(clock)
    errors, laps = [], []
    worker.failed.connect(errors.append)
    worker.lap.connect(lambda *args: laps.append(args))
    worker.run()
    assert errors == ["USB disconnected"]
    assert laps == []
    assert backend.events[-1] == ("reset", "same-device")


def test_cancel_before_start_does_not_change_location(application, clock):
    backend = FakeBackend()
    worker = RunWorker(backend, tiny_route(), 10, None)
    worker.cancel = Cancellation(clock)
    worker.stop()
    worker.run()
    assert backend.events == []


def test_progress_only_advances_after_successful_coordinate_updates(application, clock):
    backend = FakeBackend()
    worker = RunWorker(backend, tiny_route(), 10, None)
    worker.cancel = Cancellation(clock)
    updates = []
    worker.progress.connect(lambda fraction: updates.append((fraction, len(backend.events))))
    worker.lap.connect(lambda *args: worker.stop())
    worker.run()
    fractions = [entry[0] for entry in updates]
    assert fractions[0] == 0 and fractions[-1] == 1
    assert len(fractions) >= 3
    assert all(a < b for a, b in zip(fractions, fractions[1:]))
    assert [entry[1] for entry in updates] == list(range(1, len(updates) + 1))


def test_failed_coordinate_update_does_not_advance_visual_progress(application, clock):
    worker = RunWorker(FakeBackend(fail_update=True), tiny_route(), 10, None)
    worker.cancel = Cancellation(clock)
    updates = []
    worker.progress.connect(updates.append)
    worker.run()
    assert updates == []
