# SPDX-License-Identifier: MPL-2.0
"""Exercise actual worker scheduling against a virtual monotonic clock and USB delays."""
from pathlib import Path
import itertools

import pytest

from vrun.device import Device
from vrun.routes import Point, load_route
from vrun.worker import RunWorker

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


class Cancellation:
    def __init__(self, clock):
        self.clock = clock
        self.stopped = False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, duration):
        if not self.stopped:
            self.clock.now += max(0, duration)
        return self.stopped


class TimedBackend:
    def __init__(self, clock, latency):
        self.clock = clock
        self.latency = latency if callable(latency) else lambda: latency
        self.deliveries = []
        self.resets = 0

    def prepare(self, cancel, status):
        return Device("same-device", "Test iPhone", "16.7.16")

    def set_location(self, device, point, cancel):
        self.clock.now += self.latency()
        self.deliveries.append((self.clock.now, point))

    def reset(self, device):
        self.resets += 1


def run_timed(monkeypatch, route, speed, latency, laps=3):
    clock = Clock()
    # Patch only the worker module's clock, not Python's global time module.
    monkeypatch.setattr("vrun.worker.monotonic", clock.monotonic)
    backend = TimedBackend(clock, latency)
    worker = RunWorker(backend, route, speed, route.length_m * 2)
    worker.cancel = Cancellation(clock)
    completed, errors, reminders = [], [], []
    def on_lap(count, distance):
        completed.append((count, distance, clock.now))
        if count == laps:
            worker.stop()
    worker.lap.connect(on_lap)
    worker.failed.connect(errors.append)
    worker.target_reached.connect(reminders.append)
    worker.run()
    return backend, completed, errors, reminders


@pytest.mark.parametrize("name", ["HNroute.txt", "ZJG-west.txt", "ZJG-east.txt"])
@pytest.mark.parametrize("latency", [0, 0.05, 0.15, 0.3, 0.6])
@pytest.mark.parametrize("speed", [0.5, 3.3, 15.0])
def test_fixed_speed_survives_usb_command_overhead(application, monkeypatch, name, latency, speed):
    route = load_route(ROOT / "routes" / name)
    backend, completed, errors, reminders = run_timed(monkeypatch, route, speed, latency)
    assert errors == []
    origin = backend.deliveries[0][0]
    for count, distance, timestamp in completed:
        # A fraction of one USB command at a boundary is acceptable; cumulative drift is not.
        assert timestamp - origin == pytest.approx(distance / speed, abs=max(0.03, latency * 0.05))
    assert reminders == pytest.approx([route.length_m * 2])
    assert backend.resets == 1


def test_variable_latency_has_bounded_error_instead_of_accumulating(application, monkeypatch):
    route = load_route(ROOT / "routes/ZJG-east.txt")
    delays = itertools.cycle([0.03, 0.1, 0.6, 0.05, 0.3, 0.15])
    backend, completed, errors, _ = run_timed(monkeypatch, route, 3.3, lambda: next(delays), laps=8)
    assert errors == []
    origin = backend.deliveries[0][0]
    for _, distance, timestamp in completed:
        assert abs(timestamp - origin - distance / 3.3) < 0.65
    assert backend.resets == 1


def test_interpolated_deliveries_follow_speed_not_input_point_density(application, monkeypatch):
    from geopy.distance import geodesic
    from vrun.routes import Route
    def line(count):
        points = tuple(Point(30 + 0.001 * i / count, 120) for i in range(count + 1))
        points += tuple(reversed(points[:-1]))
        lengths = tuple(geodesic((a.lat, a.lng), (b.lat, b.lng)).meters for a, b in zip(points, points[1:]))
        return Route(Path("line.txt"), points, lengths)
    durations = []
    for count in (1, 1000):
        route = line(count)
        backend, completed, errors, _ = run_timed(monkeypatch, route, 3.3, 0.3, laps=1)
        assert errors == []
        origin = backend.deliveries[0][0]
        durations.append(completed[0][2] - origin)
        # On a straight section, verify speed after the initial latency estimate settles.
        for (t1, a), (t2, b) in zip(backend.deliveries, backend.deliveries[1:]):
            if t1 - origin > 3 and a.lat < 30.0008 and b.lat < 30.0008 and b.lat > a.lat:
                actual = geodesic((a.lat, a.lng), (b.lat, b.lng)).meters / (t2 - t1)
                assert actual == pytest.approx(3.3, rel=0.015)
    assert durations[0] == pytest.approx(durations[1], abs=0.03)


def test_long_transport_stall_stops_and_restores_without_counting_unvisited_laps(application, monkeypatch):
    route = load_route(ROOT / "routes/ZJG-east.txt")
    delays = iter([0.05, 0.05, 5.0])
    backend, completed, errors, reminders = run_timed(monkeypatch, route, 3.3, lambda: next(delays), laps=1)
    assert len(errors) == 1
    assert "速度" in errors[0]
    assert completed == []
    assert reminders == []
    assert backend.resets == 1
    assert len(backend.deliveries) == 3

@pytest.mark.parametrize("name", ["HNroute.txt", "ZJG-west.txt", "ZJG-east.txt"])
@pytest.mark.parametrize("speed,latency", [(3.3, 0.3), (3.3, 0.6), (15, 0.6)])
def test_speed_of_delivered_gps_track_matches_input(application, monkeypatch, name, speed, latency):
    from geopy.distance import geodesic
    route = load_route(ROOT / "routes" / name)
    backend, completed, errors, _ = run_timed(monkeypatch, route, speed, latency)
    assert errors == []
    track_m = sum(geodesic((a.lat, a.lng), (b.lat, b.lng)).meters
                  for (_, a), (_, b) in zip(backend.deliveries, backend.deliveries[1:]))
    elapsed = completed[-1][2] - backend.deliveries[0][0]
    # Position updates can cut very short corners; this checks the delivered
    # physical path, rather than accepting the application's estimated counter.
    # Tight turns/backtracks between USB updates are joined by chords. In particular,
    # 15 m/s with a 600 ms transport can omit short corners even with correct timing.
    # Bound that sampling loss, while rejecting the old 50-70% scheduling slowdown.
    assert speed * 0.90 <= track_m / elapsed <= speed * 1.01
