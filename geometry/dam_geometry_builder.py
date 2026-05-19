from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from geometry.profile_calculator import DamProfile, ProfileCalculator, ProfilePoint
from models import DamParameters


@dataclass(frozen=True)
class DamGeometry:
    profile_curve: Any
    body_brep: Any
    upstream_slope_surface: Any
    downstream_surfaces: tuple[Any, ...]
    crest_platform_surface: Any


class DamGeometryBuilder:
    """Builds Rhino geometry for a dam profile extruded along the dam axis."""

    def __init__(self, parameters: DamParameters) -> None:
        self.parameters = parameters
        self.profile = ProfileCalculator(parameters).calculate()

    def build_profile_curve(self) -> Any:
        Rhino = _require_rhino()
        points = [_to_point3d(Rhino, point) for point in self.profile.closed_points()]
        return Rhino.Geometry.PolylineCurve(points)

    def build_body_brep(self) -> Any:
        Rhino = _require_rhino()
        tolerance = _model_tolerance(Rhino)
        section_points = self.profile.points()
        faces = [
            *self._build_planar_caps(Rhino, section_points, tolerance),
            *self._build_side_faces(Rhino, section_points, tolerance),
        ]
        if any(face is None or not face.IsValid for face in faces):
            raise RuntimeError("Failed to create one or more dam body faces.")

        joined = Rhino.Geometry.Brep.JoinBreps(faces, tolerance)
        if not joined:
            raise RuntimeError("Failed to join dam body faces into a Brep.")

        body = joined[0]
        if not body.IsValid:
            raise RuntimeError("Joined dam body Brep is invalid.")
        if hasattr(body, "IsSolid") and not body.IsSolid:
            raise RuntimeError("Joined dam body Brep is not a closed solid.")

        return body

    def build_surfaces(self) -> tuple[Any, tuple[Any, ...], Any]:
        Rhino = _require_rhino()
        p = self.profile
        upstream = self._build_quad_surface(Rhino, p.upstream_toe, p.upstream_crest)
        downstream = tuple(
            self._build_quad_surface(Rhino, start, end)
            for start, end in _adjacent_pairs(p.downstream_boundary_points())
        )
        crest = self._build_quad_surface(Rhino, p.upstream_crest, p.downstream_crest)
        return upstream, downstream, crest

    def build(self) -> DamGeometry:
        upstream, downstream, crest = self.build_surfaces()
        return DamGeometry(
            profile_curve=self.build_profile_curve(),
            body_brep=self.build_body_brep(),
            upstream_slope_surface=upstream,
            downstream_surfaces=downstream,
            crest_platform_surface=crest,
        )

    def add_to_document(self, doc: Any | None = None) -> dict[str, Any]:
        Rhino = _require_rhino()
        if doc is None:
            doc = Rhino.RhinoDoc.ActiveDoc
        if doc is None:
            raise RuntimeError("No active Rhino document is available.")

        geometry = self.build()
        object_ids = {
            "profile_curve": doc.Objects.AddCurve(geometry.profile_curve),
            "body_brep": doc.Objects.AddBrep(geometry.body_brep),
            "upstream_slope_surface": doc.Objects.AddBrep(geometry.upstream_slope_surface),
            "crest_platform_surface": doc.Objects.AddBrep(geometry.crest_platform_surface),
        }
        for index, downstream_surface in enumerate(geometry.downstream_surfaces):
            object_ids[f"downstream_surface_{index}"] = doc.Objects.AddBrep(
                downstream_surface
            )
        doc.Views.Redraw()
        return object_ids

    def _build_planar_caps(
        self,
        Rhino: Any,
        section_points: tuple[ProfilePoint, ...],
        tolerance: float,
    ) -> tuple[Any, Any]:
        front_curve = self._build_profile_curve_at_y(Rhino, section_points, 0.0)
        back_curve = self._build_profile_curve_at_y(
            Rhino,
            tuple(reversed(section_points)),
            self.parameters.axis_length,
        )
        front_caps = Rhino.Geometry.Brep.CreatePlanarBreps(front_curve, tolerance)
        back_caps = Rhino.Geometry.Brep.CreatePlanarBreps(back_curve, tolerance)
        if not front_caps or not back_caps:
            raise RuntimeError("Failed to create dam body planar cap faces.")
        return front_caps[0], back_caps[0]

    def _build_side_faces(
        self,
        Rhino: Any,
        section_points: tuple[ProfilePoint, ...],
        tolerance: float,
    ) -> tuple[Any, ...]:
        return tuple(
            self._build_quad_surface(Rhino, start, end, tolerance)
            for start, end in _closed_adjacent_pairs(section_points)
        )

    def _build_profile_curve_at_y(
        self,
        Rhino: Any,
        section_points: tuple[ProfilePoint, ...],
        y: float,
    ) -> Any:
        points = [
            Rhino.Geometry.Point3d(point.x, y, point.z)
            for point in (*section_points, section_points[0])
        ]
        return Rhino.Geometry.PolylineCurve(points)

    def _build_quad_surface(
        self,
        Rhino: Any,
        start: ProfilePoint,
        end: ProfilePoint,
        tolerance: float | None = None,
    ) -> Any:
        y0 = 0.0
        y1 = self.parameters.axis_length
        if tolerance is None:
            tolerance = _model_tolerance(Rhino)
        corners = [
            Rhino.Geometry.Point3d(start.x, y0, start.z),
            Rhino.Geometry.Point3d(end.x, y0, end.z),
            Rhino.Geometry.Point3d(end.x, y1, end.z),
            Rhino.Geometry.Point3d(start.x, y1, start.z),
        ]
        brep = Rhino.Geometry.Brep.CreateFromCornerPoints(
            corners[0],
            corners[1],
            corners[2],
            corners[3],
            tolerance,
        )
        if brep is None or not brep.IsValid:
            raise RuntimeError("Failed to create a valid quad surface Brep.")
        return brep


def _to_point3d(Rhino: Any, point: ProfilePoint) -> Any:
    return Rhino.Geometry.Point3d(point.x, point.y, point.z)


def _model_tolerance(Rhino: Any) -> float:
    active_doc = Rhino.RhinoDoc.ActiveDoc
    if active_doc is None:
        return 0.001
    return active_doc.ModelAbsoluteTolerance


def _adjacent_pairs(points: tuple[ProfilePoint, ...]) -> tuple[tuple[ProfilePoint, ProfilePoint], ...]:
    return tuple(zip(points, points[1:]))


def _closed_adjacent_pairs(
    points: tuple[ProfilePoint, ...],
) -> tuple[tuple[ProfilePoint, ProfilePoint], ...]:
    return tuple(zip(points, (*points[1:], points[0])))


def _require_rhino() -> Any:
    try:
        import Rhino  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "RhinoCommon is required for geometry building. Run this module inside "
            "Rhino 8 CPython or another environment where Rhino is available."
        ) from exc
    return Rhino
