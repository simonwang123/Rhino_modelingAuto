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
    downstream_slope_surface: Any
    crest_platform_surface: Any


class DamGeometryBuilder:
    """Builds Rhino geometry for a homogeneous trapezoidal earth-rock dam."""

    def __init__(self, parameters: DamParameters) -> None:
        self.parameters = parameters
        self.profile = ProfileCalculator(parameters).calculate()

    def build_profile_curve(self) -> Any:
        Rhino = _require_rhino()
        points = [_to_point3d(Rhino, point) for point in self.profile.closed_points()]
        return Rhino.Geometry.PolylineCurve(points)

    def build_body_brep(self) -> Any:
        Rhino = _require_rhino()
        p = self.profile
        y0 = 0.0
        y1 = self.parameters.axis_length
        tolerance = _model_tolerance(Rhino)

        u0 = Rhino.Geometry.Point3d(p.upstream_toe.x, y0, p.upstream_toe.z)
        uc0 = Rhino.Geometry.Point3d(p.upstream_crest.x, y0, p.upstream_crest.z)
        dc0 = Rhino.Geometry.Point3d(p.downstream_crest.x, y0, p.downstream_crest.z)
        d0 = Rhino.Geometry.Point3d(p.downstream_toe.x, y0, p.downstream_toe.z)
        u1 = Rhino.Geometry.Point3d(p.upstream_toe.x, y1, p.upstream_toe.z)
        uc1 = Rhino.Geometry.Point3d(p.upstream_crest.x, y1, p.upstream_crest.z)
        dc1 = Rhino.Geometry.Point3d(p.downstream_crest.x, y1, p.downstream_crest.z)
        d1 = Rhino.Geometry.Point3d(p.downstream_toe.x, y1, p.downstream_toe.z)

        faces = [
            Rhino.Geometry.Brep.CreateFromCornerPoints(u0, uc0, dc0, d0, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(u1, d1, dc1, uc1, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(u0, u1, uc1, uc0, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(dc0, dc1, d1, d0, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(uc0, uc1, dc1, dc0, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(u0, d0, d1, u1, tolerance),
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

    def build_surfaces(self) -> tuple[Any, Any, Any]:
        Rhino = _require_rhino()
        p = self.profile
        upstream = self._build_quad_surface(Rhino, p.upstream_toe, p.upstream_crest)
        downstream = self._build_quad_surface(Rhino, p.downstream_crest, p.downstream_toe)
        crest = self._build_quad_surface(Rhino, p.upstream_crest, p.downstream_crest)
        return upstream, downstream, crest

    def build(self) -> DamGeometry:
        upstream, downstream, crest = self.build_surfaces()
        return DamGeometry(
            profile_curve=self.build_profile_curve(),
            body_brep=self.build_body_brep(),
            upstream_slope_surface=upstream,
            downstream_slope_surface=downstream,
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
            "downstream_slope_surface": doc.Objects.AddBrep(geometry.downstream_slope_surface),
            "crest_platform_surface": doc.Objects.AddBrep(geometry.crest_platform_surface),
        }
        doc.Views.Redraw()
        return object_ids

    def _build_quad_surface(self, Rhino: Any, start: ProfilePoint, end: ProfilePoint) -> Any:
        y0 = 0.0
        y1 = self.parameters.axis_length
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
            _model_tolerance(Rhino),
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


def _require_rhino() -> Any:
    try:
        import Rhino  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "RhinoCommon is required for geometry building. Run this module inside "
            "Rhino 8 CPython or another environment where Rhino is available."
        ) from exc
    return Rhino
