from __future__ import annotations

from dataclasses import dataclass

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

        return DamProfile(
            upstream_toe=upstream_toe,
            upstream_crest=upstream_crest,
            downstream_crest=downstream_crest,
            downstream_profile_points=downstream_profile_points,
            downstream_toe=downstream_toe,
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
