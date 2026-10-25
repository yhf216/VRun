# SPDX-License-Identifier: MPL-2.0
"""Route parsing and closed-loop distance estimates. Coordinates are WGS-84 internally."""
from dataclasses import dataclass
from pathlib import Path
import ast
import math
from bisect import bisect_right
from functools import cached_property
from itertools import accumulate

from geopy.distance import geodesic

from .coordinates import bd09_to_wgs84


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float


@dataclass(frozen=True)
class Route:
    path: Path
    points: tuple[Point, ...]
    segment_lengths: tuple[float, ...]

    @property
    def length_m(self) -> float:
        return self.cumulative_lengths[-1]

    @cached_property
    def cumulative_lengths(self) -> tuple[float, ...]:
        return tuple(accumulate(self.segment_lengths, initial=0.0))

    def position_at(self, distance_m: float) -> Point:
        """Interpolate by travelled arc length, independent of route point density."""
        if not math.isfinite(distance_m):
            raise ValueError("路线距离必须是有限数值")
        if distance_m <= 0:
            return self.points[0]
        if distance_m >= self.length_m:
            return self.points[-1]
        segment = bisect_right(self.cumulative_lengths, distance_m) - 1
        start, end = self.points[segment:segment + 2]
        ratio = (distance_m - self.cumulative_lengths[segment]) / self.segment_lengths[segment]
        return Point(start.lat + (end.lat - start.lat) * ratio,
                     start.lng + (end.lng - start.lng) * ratio)

    def samples(self, speed: float, interval: float = 0.25):
        """Yield interpolated points and time deltas, including the closing segment."""
        if not math.isfinite(speed) or speed <= 0 or interval <= 0:
            raise ValueError("速度和更新间隔必须大于零")
        for start, end, distance in zip(self.points, self.points[1:], self.segment_lengths):
            if distance <= 0:
                continue
            duration = distance / speed
            count = max(1, math.ceil(duration / interval))
            for index in range(1, count + 1):
                ratio = index / count
                yield Point(start.lat + (end.lat - start.lat) * ratio,
                            start.lng + (end.lng - start.lng) * ratio), duration / count


def load_route(path: Path) -> Route:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("路线文件过大，请使用小于 2 MB 的文件")
    try:
        records = ast.literal_eval(path.read_text(encoding="utf-8-sig").strip())
    except (ValueError, SyntaxError, RecursionError) as error:
        raise ValueError("路线格式不正确，需要包含 lat、lng 的坐标列表") from error
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, (list, tuple)) or not 2 <= len(records) <= 20000:
        raise ValueError("路线需要包含 2 至 20000 个坐标点")
    points = []
    for record in records:
        try:
            if not isinstance(record, dict) or isinstance(record["lat"], bool) or isinstance(record["lng"], bool):
                raise ValueError
            lat, lng = float(record["lat"]), float(record["lng"])
            if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError("路线包含无效坐标，请检查 lat、lng") from error
        converted = bd09_to_wgs84({"lat": lat, "lng": lng})
        point = Point(converted["lat"], converted["lng"])
        if not points or point != points[-1]:
            points.append(point)
    if len(points) < 2:
        raise ValueError("路线需要至少两个不同的坐标点")
    if points[-1] != points[0]:
        points.append(points[0])
    lengths = tuple(geodesic((a.lat, a.lng), (b.lat, b.lng)).meters for a, b in zip(points, points[1:]))
    if sum(lengths) < 1:
        raise ValueError("路线总长度不足 1 米")
    return Route(path, tuple(points), lengths)


def pace_text(speed: float) -> str:
    if not math.isfinite(speed) or speed <= 0:
        return "—"
    seconds = round(1000 / speed)
    return f"{seconds // 60}:{seconds % 60:02d} / 公里"


@dataclass
class LapCounter:
    lap_length_m: float
    target_m: float | None = None
    laps: int = 0
    notified: bool = False

    @property
    def distance_m(self) -> float:
        return self.laps * self.lap_length_m

    def complete_lap(self) -> bool:
        self.laps += 1
        reached = self.target_m is not None and self.distance_m >= self.target_m and not self.notified
        if reached:
            self.notified = True
        return reached
