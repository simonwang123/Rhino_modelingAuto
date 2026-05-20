from __future__ import annotations

from dataclasses import dataclass

from geometry.section_polygon import (
    GEOMETRY_TOLERANCE,
    SectionPoint,
    SectionPolygon,
    point_on_segment,
    polygon_is_simple,
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

    def closed_points(self) -> tuple[ProfilePoint, ...]:
        return (*self.points, self.points[0])


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
        zone_polygon = SectionPolygon(section_points)
        if zone_polygon.area <= GEOMETRY_TOLERANCE:
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

        return RockfillZoneProfile(
            points=(
                zone_points[0],
                zone_points[1],
                zone_points[2],
                zone_points[3],
            )
        )


def _point_on_open_boundary(
    point: SectionPoint,
    boundary_points: tuple[SectionPoint, ...],
) -> bool:
    return any(
        point_on_segment(point, start, end)
        for start, end in zip(boundary_points, boundary_points[1:])
    )


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
