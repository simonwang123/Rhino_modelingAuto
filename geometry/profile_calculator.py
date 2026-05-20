from __future__ import annotations

from dataclasses import dataclass

from geometry.section_polygon import (
    GEOMETRY_TOLERANCE,
    SectionPoint,
    SectionPolygon,
    point_on_segment,
    points_equal,
    polygon_is_simple,
    segments_intersect,
)
from models import DamParameters


@dataclass(frozen=True)
class ProfilePoint:
    """A Rhino-independent point in the dam cross-section."""

    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class DamProfile:
    """Ordered points of the dam cross-section."""

    upstream_toe: ProfilePoint
    upstream_crest: ProfilePoint
    downstream_crest: ProfilePoint
    downstream_profile_points: tuple[ProfilePoint, ...]
    downstream_toe: ProfilePoint
    secondary_rockfill_zone: "RockfillZoneProfile | None" = None

    def points(self) -> tuple[ProfilePoint, ...]:
        return (
            self.upstream_toe,
            self.upstream_crest,
            self.downstream_crest,
            *self.downstream_profile_points,
            self.downstream_toe,
        )

    def closed_points(self) -> tuple[ProfilePoint, ...]:
        return (*self.points(), self.upstream_toe)

    def downstream_boundary_points(self) -> tuple[ProfilePoint, ...]:
        return (
            self.downstream_crest,
            *self.downstream_profile_points,
            self.downstream_toe,
        )


@dataclass(frozen=True)
class RockfillZoneProfile:
    """A user-defined rockfill zone in the dam section."""

    points: tuple[ProfilePoint, ProfilePoint, ProfilePoint, ProfilePoint]
    boundary: tuple[ProfilePoint, ...]

    def boundary_points(self) -> tuple[ProfilePoint, ...]:
        return self.boundary

    def closed_points(self) -> tuple[ProfilePoint, ...]:
        return (*self.boundary, self.boundary[0])


class ProfileCalculator:
    """Calculates the dam cross-section without depending on RhinoCommon."""

    def __init__(self, parameters: DamParameters) -> None:
        self.parameters = parameters

    def calculate(self) -> DamProfile:
        params = self.parameters
        height = params.calculated_height
        half_crest_width = params.crest_width / 2.0
        upstream_offset = params.upstream_slope * height

        upstream_toe = ProfilePoint(
            x=-(half_crest_width + upstream_offset),
            y=0.0,
            z=params.foundation_elevation,
        )
        upstream_crest = ProfilePoint(
            x=-half_crest_width,
            y=0.0,
            z=params.crest_elevation,
        )
        downstream_crest = ProfilePoint(
            x=half_crest_width,
            y=0.0,
            z=params.crest_elevation,
        )
        downstream_profile_points, downstream_toe = self._calculate_downstream_profile(
            downstream_crest
        )

        profile = DamProfile(
            upstream_toe=upstream_toe,
            upstream_crest=upstream_crest,
            downstream_crest=downstream_crest,
            downstream_profile_points=downstream_profile_points,
            downstream_toe=downstream_toe,
        )
        secondary_zone = self._calculate_secondary_rockfill_zone(profile)

        return DamProfile(
            upstream_toe=profile.upstream_toe,
            upstream_crest=profile.upstream_crest,
            downstream_crest=profile.downstream_crest,
            downstream_profile_points=profile.downstream_profile_points,
            downstream_toe=profile.downstream_toe,
            secondary_rockfill_zone=secondary_zone,
        )

    def _calculate_downstream_profile(
        self,
        downstream_crest: ProfilePoint,
    ) -> tuple[tuple[ProfilePoint, ...], ProfilePoint]:
        params = self.parameters
        current_x = downstream_crest.x
        current_z = downstream_crest.z
        profile_points: list[ProfilePoint] = []

        for bench_elevation in params.bench_elevations or ():
            slope_run = params.downstream_slope * (current_z - bench_elevation)
            current_x += slope_run
            current_z = bench_elevation
            profile_points.append(ProfilePoint(x=current_x, y=0.0, z=current_z))

            current_x += params.bench_width
            profile_points.append(ProfilePoint(x=current_x, y=0.0, z=current_z))

        final_slope_run = params.downstream_slope * (
            current_z - params.foundation_elevation
        )
        downstream_toe = ProfilePoint(
            x=current_x + final_slope_run,
            y=0.0,
            z=params.foundation_elevation,
        )

        return tuple(profile_points), downstream_toe

    def _calculate_secondary_rockfill_zone(
        self,
        dam_profile: DamProfile,
    ) -> RockfillZoneProfile | None:
        points = self.parameters.secondary_rockfill_points
        if points is None:
            return None

        zone_points = tuple(ProfilePoint(x=x, y=0.0, z=z) for x, z in points)
        section_points = tuple(SectionPoint(point.x, point.z) for point in zone_points)
        control_polygon = SectionPolygon(section_points)
        if control_polygon.area <= GEOMETRY_TOLERANCE:
            raise ValueError("secondary_rockfill_points must form a polygon with positive area.")
        if len(set(point.as_tuple() for point in section_points)) != len(section_points):
            raise ValueError("secondary_rockfill_points must not contain duplicate points.")
        if not polygon_is_simple(section_points):
            raise ValueError("secondary_rockfill_points must form a non-self-intersecting polygon.")

        dam_polygon = SectionPolygon(
            tuple(SectionPoint(point.x, point.z) for point in dam_profile.points())
        )
        left_points, right_points = _classify_zone_side_points(section_points)

        for point in left_points:
            if not dam_polygon.contains_point_strict(point):
                raise ValueError(
                    "The two left secondary_rockfill_points must be strictly inside "
                    "the dam section."
                )

        downstream_boundary = tuple(
            SectionPoint(point.x, point.z)
            for point in dam_profile.downstream_boundary_points()
        )
        for point in right_points:
            if dam_polygon.contains_point_strict(point):
                continue
            if _point_on_open_boundary(point, downstream_boundary):
                continue
            raise ValueError(
                "The two right secondary_rockfill_points must be inside the dam section "
                "or on the downstream boundary."
            )

        boundary_points = _build_secondary_zone_boundary(
            section_points,
            right_points,
            dam_polygon,
            downstream_boundary,
        )
        boundary_polygon = SectionPolygon(boundary_points)
        if boundary_polygon.area <= GEOMETRY_TOLERANCE:
            raise ValueError("secondary_rockfill_points must form a polygon with positive area.")
        if not polygon_is_simple(boundary_points):
            raise ValueError(
                "secondary_rockfill_points actual boundary must be non-self-intersecting."
            )

        return RockfillZoneProfile(
            points=(
                zone_points[0],
                zone_points[1],
                zone_points[2],
                zone_points[3],
            ),
            boundary=tuple(ProfilePoint(point.x, 0.0, point.z) for point in boundary_points),
        )


def _point_on_open_boundary(
    point: SectionPoint,
    boundary_points: tuple[SectionPoint, ...],
) -> bool:
    return any(
        point_on_segment(point, start, end)
        for start, end in zip(boundary_points, boundary_points[1:])
    )


def _build_secondary_zone_boundary(
    control_points: tuple[SectionPoint, SectionPoint, SectionPoint, SectionPoint],
    right_edge: tuple[SectionPoint, SectionPoint],
    dam_polygon: SectionPolygon,
    downstream_boundary: tuple[SectionPoint, ...],
) -> tuple[SectionPoint, ...]:
    right_start, right_end = right_edge
    if _point_on_open_boundary(
        right_start,
        downstream_boundary,
    ) and _point_on_open_boundary(right_end, downstream_boundary):
        right_path = _extract_downstream_boundary_path(
            right_start,
            right_end,
            downstream_boundary,
        )
    else:
        _validate_internal_right_edge(
            right_start,
            right_end,
            dam_polygon,
            downstream_boundary,
        )
        right_path = right_edge

    right_edge_index = _find_directed_edge_index(control_points, right_edge)
    boundary: list[SectionPoint] = []
    for offset in range(len(control_points)):
        index = (right_edge_index + 1 + offset) % len(control_points)
        boundary.append(control_points[index])
        next_index = (index + 1) % len(control_points)
        if (control_points[index], control_points[next_index]) == right_edge:
            boundary.extend(right_path[1:])
            break
    return _remove_consecutive_duplicate_points(tuple(boundary))


def _extract_downstream_boundary_path(
    start: SectionPoint,
    end: SectionPoint,
    boundary: tuple[SectionPoint, ...],
) -> tuple[SectionPoint, ...]:
    start_station = _station_on_polyline(start, boundary)
    end_station = _station_on_polyline(end, boundary)
    if start_station is None or end_station is None:
        raise ValueError("Both right boundary points must lie on the downstream boundary.")

    if start_station <= end_station:
        middle = tuple(
            point
            for point in boundary
            if start_station < _station_on_polyline_vertex(point, boundary) < end_station
        )
        return _remove_consecutive_duplicate_points((start, *middle, end))

    middle = tuple(
        point
        for point in reversed(boundary)
        if end_station < _station_on_polyline_vertex(point, boundary) < start_station
    )
    return _remove_consecutive_duplicate_points((start, *middle, end))


def _validate_internal_right_edge(
    start: SectionPoint,
    end: SectionPoint,
    dam_polygon: SectionPolygon,
    downstream_boundary: tuple[SectionPoint, ...],
) -> None:
    sample_parameters = (0.25, 0.5, 0.75)
    for parameter in sample_parameters:
        point = _interpolate(start, end, parameter)
        if not dam_polygon.contains_point_or_boundary(point):
            raise ValueError(
                "The straight right edge of secondary_rockfill_points must stay inside "
                "the dam section."
            )

    for boundary_start, boundary_end in zip(downstream_boundary, downstream_boundary[1:]):
        if not segments_intersect(start, end, boundary_start, boundary_end):
            continue
        if point_on_segment(start, boundary_start, boundary_end) or point_on_segment(
            end,
            boundary_start,
            boundary_end,
        ):
            continue
        raise ValueError(
            "The straight right edge of secondary_rockfill_points must not intersect "
            "the downstream boundary."
        )


def _find_directed_edge_index(
    points: tuple[SectionPoint, SectionPoint, SectionPoint, SectionPoint],
    edge: tuple[SectionPoint, SectionPoint],
) -> int:
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if points_equal(start, edge[0]) and points_equal(end, edge[1]):
            return index
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if points_equal(start, edge[1]) and points_equal(end, edge[0]):
            return index
    raise ValueError("secondary_rockfill_points right side must be an input polygon edge.")


def _station_on_polyline(
    point: SectionPoint,
    boundary: tuple[SectionPoint, ...],
) -> float | None:
    station = 0.0
    for start, end in zip(boundary, boundary[1:]):
        segment_length = _distance(start, end)
        if point_on_segment(point, start, end):
            return station + _distance(start, point)
        station += segment_length
    return None


def _station_on_polyline_vertex(
    point: SectionPoint,
    boundary: tuple[SectionPoint, ...],
) -> float:
    station = _station_on_polyline(point, boundary)
    if station is None:
        raise ValueError("Boundary vertex is not on its polyline.")
    return station


def _interpolate(start: SectionPoint, end: SectionPoint, parameter: float) -> SectionPoint:
    return SectionPoint(
        x=start.x + (end.x - start.x) * parameter,
        z=start.z + (end.z - start.z) * parameter,
    )


def _distance(start: SectionPoint, end: SectionPoint) -> float:
    return ((end.x - start.x) ** 2 + (end.z - start.z) ** 2) ** 0.5


def _remove_consecutive_duplicate_points(
    points: tuple[SectionPoint, ...],
) -> tuple[SectionPoint, ...]:
    deduped: list[SectionPoint] = []
    for point in points:
        if not deduped or not points_equal(deduped[-1], point):
            deduped.append(point)
    if len(deduped) > 1 and points_equal(deduped[0], deduped[-1]):
        deduped.pop()
    return tuple(deduped)


def _classify_zone_side_points(
    points: tuple[SectionPoint, SectionPoint, SectionPoint, SectionPoint],
) -> tuple[tuple[SectionPoint, SectionPoint], tuple[SectionPoint, SectionPoint]]:
    opposite_edge_pairs = (
        ((points[0], points[1]), (points[2], points[3])),
        ((points[1], points[2]), (points[3], points[0])),
    )
    side_edges = max(
        opposite_edge_pairs,
        key=lambda pair: _edge_vertical_span(pair[0]) + _edge_vertical_span(pair[1]),
    )
    first_edge, second_edge = side_edges
    first_average_x = _edge_average_x(first_edge)
    second_average_x = _edge_average_x(second_edge)
    if abs(first_average_x - second_average_x) <= GEOMETRY_TOLERANCE:
        raise ValueError("secondary_rockfill_points side edges must have distinct x positions.")
    if first_average_x < second_average_x:
        return first_edge, second_edge
    return second_edge, first_edge


def _edge_vertical_span(edge: tuple[SectionPoint, SectionPoint]) -> float:
    return abs(edge[0].z - edge[1].z)


def _edge_average_x(edge: tuple[SectionPoint, SectionPoint]) -> float:
    return (edge[0].x + edge[1].x) / 2.0
