from __future__ import annotations

from typing import Any

from models import TerrainContour


def sample_curve_to_terrain_contour(
    curve: Any,
    elevation: float,
    sample_interval: float = 10.0,
) -> TerrainContour:
    """Sample a Rhino curve into a TerrainContour by arc-length interval."""

    if sample_interval <= 0:
        raise ValueError("sample_interval must be positive.")
    if curve is None:
        raise ValueError("curve is required.")
    if not hasattr(curve, "GetLength") or not hasattr(curve, "PointAtLength"):
        raise TypeError("curve must be a Rhino.Geometry.Curve-like object.")

    length = curve.GetLength()
    if length <= 0:
        raise ValueError("curve length must be positive.")

    distances = [0.0]
    current_distance = sample_interval
    while current_distance < length:
        distances.append(current_distance)
        current_distance += sample_interval
    if distances[-1] != length:
        distances.append(length)

    points = tuple(_point_at_length(curve, distance) for distance in distances)
    return TerrainContour(elevation=elevation, points=points)


def _point_at_length(curve: Any, distance: float) -> tuple[float, float, float]:
    point = curve.PointAtLength(distance)
    return (float(point.X), float(point.Y), float(point.Z))
