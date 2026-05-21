from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Optional

from .construction_stage import ConstructionStage
from .terrain_boundary import TerrainBoundary


@dataclass(frozen=True)
class DamParameters:
    """Core design parameters for an earth-rock dam profile."""

    dam_height: float
    crest_width: float
    upstream_slope: float
    downstream_slope: float
    axis_length: float
    foundation_elevation: float
    crest_elevation: float
    cushion_layer_top_thickness: float = 0.0
    cushion_layer_bottom_thickness: float = 0.0
    transition_layer_top_thickness: float = 0.0
    transition_layer_bottom_thickness: float = 0.0
    bench_count: int = 0
    bench_elevations: Optional[tuple[float, ...]] = None
    bench_width: float = 0.0
    secondary_rockfill_points: Optional[tuple[tuple[float, float], ...]] = None
    terrain_boundary: Optional[TerrainBoundary] = None
    construction_stage_top_elevations: Optional[tuple[float, ...]] = None

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

        if self.bench_count < 0:
            raise ValueError(f"bench_count must be non-negative, got {self.bench_count!r}.")
        if self.bench_count > 0 and self.bench_width <= 0:
            raise ValueError("bench_width must be positive when bench_count is greater than 0.")
        if self.bench_count == 0 and self.bench_width != 0:
            raise ValueError("bench_width must be 0 when bench_count is 0.")

        self._validate_upstream_layer_thicknesses()
        normalized_elevations = self._normalized_bench_elevations()
        object.__setattr__(self, "bench_elevations", normalized_elevations)

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

        self._validate_terrain_boundary()
        normalized_stage_elevations = self._normalized_construction_stage_top_elevations()
        object.__setattr__(
            self,
            "construction_stage_top_elevations",
            normalized_stage_elevations,
        )

        normalized_secondary_points = self._normalized_secondary_rockfill_points()
        object.__setattr__(
            self,
            "secondary_rockfill_points",
            normalized_secondary_points,
        )

    @property
    def calculated_height(self) -> float:
        return self.crest_elevation - self.foundation_elevation

    @property
    def construction_stages(self) -> tuple[ConstructionStage, ...]:
        if self.construction_stage_top_elevations is None:
            return ()

        stages: list[ConstructionStage] = []
        bottom_elevation = self.foundation_elevation
        for index, top_elevation in enumerate(
            self.construction_stage_top_elevations,
            start=1,
        ):
            stages.append(
                ConstructionStage(
                    stage_index=index,
                    bottom_elevation=bottom_elevation,
                    top_elevation=top_elevation,
                )
            )
            bottom_elevation = top_elevation
        return tuple(stages)

    def _normalized_bench_elevations(self) -> tuple[float, ...]:
        if self.bench_count == 0:
            if self.bench_elevations not in (None, ()):
                raise ValueError("bench_elevations must be empty when bench_count is 0.")
            return ()

        if self.bench_elevations is None:
            interval = self.dam_height / (self.bench_count + 1)
            return tuple(
                self.crest_elevation - interval * index
                for index in range(1, self.bench_count + 1)
            )

        if len(self.bench_elevations) != self.bench_count:
            raise ValueError(
                "bench_elevations length must equal bench_count; "
                f"got {len(self.bench_elevations)} elevations for {self.bench_count} benches."
            )

        sorted_elevations = tuple(sorted(self.bench_elevations, reverse=True))
        for elevation in sorted_elevations:
            if not self.foundation_elevation < elevation < self.crest_elevation:
                raise ValueError(
                    "bench_elevations must be strictly between foundation_elevation "
                    f"and crest_elevation; got {elevation!r}."
                )

        return sorted_elevations

    def _normalized_secondary_rockfill_points(
        self,
    ) -> Optional[tuple[tuple[float, float], ...]]:
        if self.secondary_rockfill_points in (None, ()):
            return None

        if len(self.secondary_rockfill_points) != 4:
            raise ValueError(
                "secondary_rockfill_points must be empty or contain exactly 4 points."
            )

        normalized_points: list[tuple[float, float]] = []
        for point in self.secondary_rockfill_points:
            if len(point) != 2:
                raise ValueError(
                    "Each secondary_rockfill_points item must contain exactly 2 values: (x, z)."
                )
            x, z = float(point[0]), float(point[1])
            if not self.foundation_elevation <= z <= self.crest_elevation:
                raise ValueError(
                    "secondary_rockfill_points elevations must be within the dam height; "
                    f"got z={z!r}."
                )
            normalized_points.append((x, z))

        return tuple(normalized_points)

    def _validate_upstream_layer_thicknesses(self) -> None:
        cushion_enabled = self._layer_thickness_pair_enabled(
            self.cushion_layer_top_thickness,
            self.cushion_layer_bottom_thickness,
            "cushion_layer",
        )
        transition_enabled = self._layer_thickness_pair_enabled(
            self.transition_layer_top_thickness,
            self.transition_layer_bottom_thickness,
            "transition_layer",
        )
        if transition_enabled and not cushion_enabled:
            raise ValueError("transition_layer requires cushion_layer to be enabled.")

    def _validate_terrain_boundary(self) -> None:
        if self.terrain_boundary is None:
            return

        elevations = self.terrain_boundary.elevations
        if not isclose(
            elevations[0],
            self.foundation_elevation,
            rel_tol=0.0,
            abs_tol=self.ELEVATION_TOLERANCE,
        ):
            raise ValueError(
                "terrain_boundary lowest elevation must equal foundation_elevation."
            )
        if not isclose(
            elevations[-1],
            self.crest_elevation,
            rel_tol=0.0,
            abs_tol=self.ELEVATION_TOLERANCE,
        ):
            raise ValueError("terrain_boundary highest elevation must equal crest_elevation.")

        for contour in (
            *self.terrain_boundary.left_bank_contours,
            *self.terrain_boundary.right_bank_contours,
        ):
            for point in contour.points:
                if not 0.0 <= point[1] <= self.axis_length:
                    raise ValueError(
                        "terrain_boundary point y values must be within the dam axis length."
                    )

    def _normalized_construction_stage_top_elevations(
        self,
    ) -> Optional[tuple[float, ...]]:
        if self.construction_stage_top_elevations in (None, ()):
            return None

        normalized_elevations = tuple(
            float(elevation) for elevation in self.construction_stage_top_elevations
        )
        previous_elevation = self.foundation_elevation
        for elevation in normalized_elevations:
            if elevation <= self.foundation_elevation:
                raise ValueError(
                    "construction_stage_top_elevations must be greater than "
                    "foundation_elevation."
                )
            if elevation > self.crest_elevation:
                raise ValueError(
                    "construction_stage_top_elevations must not exceed crest_elevation."
                )
            if elevation <= previous_elevation:
                raise ValueError(
                    "construction_stage_top_elevations must be strictly increasing."
                )
            previous_elevation = elevation

        if not isclose(
            normalized_elevations[-1],
            self.crest_elevation,
            rel_tol=0.0,
            abs_tol=self.ELEVATION_TOLERANCE,
        ):
            raise ValueError(
                "construction_stage_top_elevations last value must equal crest_elevation."
            )
        return normalized_elevations

    @staticmethod
    def _layer_thickness_pair_enabled(
        top_thickness: float,
        bottom_thickness: float,
        layer_name: str,
    ) -> bool:
        if top_thickness < 0 or bottom_thickness < 0:
            raise ValueError(f"{layer_name} thicknesses must be non-negative.")
        if top_thickness == 0 and bottom_thickness == 0:
            return False
        if top_thickness <= 0 or bottom_thickness <= 0:
            raise ValueError(
                f"{layer_name} top and bottom thicknesses must both be positive "
                "when the layer is enabled."
            )
        return True
