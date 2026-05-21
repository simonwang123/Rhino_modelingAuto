from __future__ import annotations

from dataclasses import dataclass


TERRAIN_ELEVATION_TOLERANCE = 1e-6
TerrainPoint = tuple[float, float, float]


@dataclass(frozen=True)
class TerrainContour:
    """A sampled terrain contour at one elevation."""

    elevation: float
    points: tuple[TerrainPoint, ...]

    def __post_init__(self) -> None:
        elevation = float(self.elevation)
        object.__setattr__(self, "elevation", elevation)

        if len(self.points) < 2:
            raise ValueError("terrain contour must contain at least 2 points.")

        normalized_points: list[TerrainPoint] = []
        for point in self.points:
            if len(point) != 3:
                raise ValueError("terrain contour points must contain exactly 3 values.")
            x, y, z = float(point[0]), float(point[1]), float(point[2])
            if abs(z - elevation) > TERRAIN_ELEVATION_TOLERANCE:
                raise ValueError(
                    "terrain contour point z values must match the contour elevation."
                )
            normalized_points.append((x, y, z))

        object.__setattr__(self, "points", tuple(normalized_points))


@dataclass(frozen=True)
class TerrainBoundary:
    """Left and right bank terrain contours used to constrain dam geometry."""

    left_bank_contours: tuple[TerrainContour, ...]
    right_bank_contours: tuple[TerrainContour, ...]
    sample_interval: float = 10.0

    def __post_init__(self) -> None:
        if self.sample_interval <= 0:
            raise ValueError("terrain sample_interval must be positive.")
        if len(self.left_bank_contours) < 2:
            raise ValueError("left_bank_contours must contain at least 2 contours.")
        if len(self.right_bank_contours) < 2:
            raise ValueError("right_bank_contours must contain at least 2 contours.")

        left = tuple(sorted(self.left_bank_contours, key=lambda contour: contour.elevation))
        right = tuple(sorted(self.right_bank_contours, key=lambda contour: contour.elevation))
        _validate_unique_elevations(left, "left_bank_contours")
        _validate_unique_elevations(right, "right_bank_contours")

        left_elevations = tuple(contour.elevation for contour in left)
        right_elevations = tuple(contour.elevation for contour in right)
        if left_elevations != right_elevations:
            raise ValueError(
                "left_bank_contours and right_bank_contours must use the same elevations."
            )

        for left_contour, right_contour in zip(left, right):
            if _average_y(left_contour) >= _average_y(right_contour):
                raise ValueError(
                    "left_bank_contours must lie before right_bank_contours along the Y axis."
                )

        object.__setattr__(self, "left_bank_contours", left)
        object.__setattr__(self, "right_bank_contours", right)

    @property
    def elevations(self) -> tuple[float, ...]:
        return tuple(contour.elevation for contour in self.left_bank_contours)


def _validate_unique_elevations(
    contours: tuple[TerrainContour, ...],
    field_name: str,
) -> None:
    elevations = tuple(contour.elevation for contour in contours)
    if len(set(elevations)) != len(elevations):
        raise ValueError(f"{field_name} elevations must be unique.")


def _average_y(contour: TerrainContour) -> float:
    return sum(point[1] for point in contour.points) / len(contour.points)
