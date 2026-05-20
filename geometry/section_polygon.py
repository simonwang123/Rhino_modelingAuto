from __future__ import annotations

from dataclasses import dataclass


GEOMETRY_TOLERANCE = 1e-7


@dataclass(frozen=True)
class SectionPoint:
    """A 2D point in the dam section plane."""

    x: float
    z: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.z)


class SectionPolygon:
    """Small polygon helper for Rhino-independent section validation."""

    def __init__(self, points: tuple[SectionPoint, ...]) -> None:
        if len(points) < 3:
            raise ValueError("A section polygon requires at least 3 points.")
        self.points = points

    @property
    def area(self) -> float:
        signed = 0.0
        for start, end in self.closed_edges():
            signed += start.x * end.z - end.x * start.z
        return abs(signed) / 2.0

    def closed_edges(self) -> tuple[tuple[SectionPoint, SectionPoint], ...]:
        return tuple(zip(self.points, (*self.points[1:], self.points[0])))

    def contains_point_strict(self, point: SectionPoint) -> bool:
        if self.on_boundary(point):
            return False
        return self.contains_point_or_boundary(point)

    def contains_point_or_boundary(self, point: SectionPoint) -> bool:
        if self.on_boundary(point):
            return True

        inside = False
        previous = self.points[-1]
        for current in self.points:
            crosses = (current.z > point.z) != (previous.z > point.z)
            if crosses:
                x_intersection = (previous.x - current.x) * (
                    point.z - current.z
                ) / (previous.z - current.z) + current.x
                if point.x < x_intersection:
                    inside = not inside
            previous = current
        return inside

    def on_boundary(self, point: SectionPoint) -> bool:
        return any(point_on_segment(point, start, end) for start, end in self.closed_edges())


def point_on_segment(
    point: SectionPoint,
    start: SectionPoint,
    end: SectionPoint,
    tolerance: float = GEOMETRY_TOLERANCE,
) -> bool:
    cross = (point.z - start.z) * (end.x - start.x) - (point.x - start.x) * (
        end.z - start.z
    )
    if abs(cross) > tolerance:
        return False

    min_x = min(start.x, end.x) - tolerance
    max_x = max(start.x, end.x) + tolerance
    min_z = min(start.z, end.z) - tolerance
    max_z = max(start.z, end.z) + tolerance
    return min_x <= point.x <= max_x and min_z <= point.z <= max_z


def polygon_is_simple(points: tuple[SectionPoint, ...]) -> bool:
    edges = tuple(zip(points, (*points[1:], points[0])))
    for index, first in enumerate(edges):
        for other_index, second in enumerate(edges[index + 1 :], start=index + 1):
            if _edges_are_adjacent(index, other_index, len(edges)):
                continue
            if segments_intersect(first[0], first[1], second[0], second[1]):
                return False
    return True


def segments_intersect(
    a: SectionPoint,
    b: SectionPoint,
    c: SectionPoint,
    d: SectionPoint,
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if o1 != o2 and o3 != o4:
        return True

    return (
        o1 == 0
        and point_on_segment(c, a, b)
        or o2 == 0
        and point_on_segment(d, a, b)
        or o3 == 0
        and point_on_segment(a, c, d)
        or o4 == 0
        and point_on_segment(b, c, d)
    )


def _orientation(a: SectionPoint, b: SectionPoint, c: SectionPoint) -> int:
    value = (b.z - a.z) * (c.x - b.x) - (b.x - a.x) * (c.z - b.z)
    if abs(value) <= GEOMETRY_TOLERANCE:
        return 0
    return 1 if value > 0 else 2


def _edges_are_adjacent(first_index: int, second_index: int, edge_count: int) -> bool:
    return (
        abs(first_index - second_index) == 1
        or {first_index, second_index} == {0, edge_count - 1}
    )
