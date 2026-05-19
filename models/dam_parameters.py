from __future__ import annotations

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class DamParameters:
    """Core design parameters for a homogeneous earth-rock dam."""

    dam_height: float
    crest_width: float
    upstream_slope: float
    downstream_slope: float
    axis_length: float
    foundation_elevation: float
    crest_elevation: float

    ELEVATION_TOLERANCE = 1e-6

    def __post_init__(self) -> None:
        positive_fields = (
            "dam_height",
            "crest_width",
            "upstream_slope",
            "downstream_slope",
            "axis_length",
        )
        for field_name in positive_fields:
            value = getattr(self, field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be positive, got {value!r}.")

        elevation_height = self.crest_elevation - self.foundation_elevation
        if not isclose(
            elevation_height,
            self.dam_height,
            rel_tol=0.0,
            abs_tol=self.ELEVATION_TOLERANCE,
        ):
            raise ValueError(
                "crest_elevation - foundation_elevation must equal dam_height "
                f"within {self.ELEVATION_TOLERANCE}; got {elevation_height!r}."
            )

    @property
    def calculated_height(self) -> float:
        return self.crest_elevation - self.foundation_elevation
