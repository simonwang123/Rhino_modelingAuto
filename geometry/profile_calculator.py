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
    """Ordered points of the trapezoidal dam cross-section."""

    upstream_toe: ProfilePoint
    upstream_crest: ProfilePoint
    downstream_crest: ProfilePoint
    downstream_toe: ProfilePoint

    def points(self) -> tuple[ProfilePoint, ProfilePoint, ProfilePoint, ProfilePoint]:
        return (
            self.upstream_toe,
            self.upstream_crest,
            self.downstream_crest,
            self.downstream_toe,
        )

    def closed_points(self) -> tuple[ProfilePoint, ...]:
        return (*self.points(), self.upstream_toe)


class ProfileCalculator:
    """Calculates the dam cross-section without depending on RhinoCommon."""

    def __init__(self, parameters: DamParameters) -> None:
        self.parameters = parameters

    def calculate(self) -> DamProfile:
        params = self.parameters
        height = params.calculated_height
        half_crest_width = params.crest_width / 2.0
        upstream_offset = params.upstream_slope * height
        downstream_offset = params.downstream_slope * height

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
        downstream_toe = ProfilePoint(
            x=half_crest_width + downstream_offset,
            y=0.0,
            z=params.foundation_elevation,
        )

        return DamProfile(
            upstream_toe=upstream_toe,
            upstream_crest=upstream_crest,
            downstream_crest=downstream_crest,
            downstream_toe=downstream_toe,
        )
