from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from geometry.profile_calculator import DamProfile, ProfileCalculator, ProfilePoint
from models import ConstructionStage, DamParameters, TerrainBoundary, TerrainContour


@dataclass(frozen=True)
class ConstructionStagePart:
    zone_name: str
    breps: tuple[Any, ...]


@dataclass(frozen=True)
class ConstructionStageGeometry:
    stage: ConstructionStage
    parts: tuple[ConstructionStagePart, ...]


@dataclass(frozen=True)
class DamGeometry:
    profile_curve: Any | None
    body_brep: Any
    primary_rockfill_brep: Any
    secondary_rockfill_brep: Any | None
    cushion_layer_brep: Any | None
    transition_layer_brep: Any | None
    secondary_rockfill_profile_curve: Any | None
    upstream_slope_surface: Any | None
    downstream_surfaces: tuple[Any, ...]
    crest_platform_surface: Any | None
    construction_stages: tuple[ConstructionStageGeometry, ...]


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
        return self._build_section_brep(Rhino, self.profile.points())

    def build_secondary_rockfill_profile_curve(self) -> Any | None:
        Rhino = _require_rhino()
        if self.profile.secondary_rockfill_zone is None:
            return None
        points = [
            _to_point3d(Rhino, point)
            for point in self.profile.secondary_rockfill_zone.closed_points()
        ]
        return Rhino.Geometry.PolylineCurve(points)

    def build_secondary_rockfill_brep(self) -> Any | None:
        Rhino = _require_rhino()
        if self.profile.secondary_rockfill_zone is None:
            return None
        return self._build_section_brep(
            Rhino,
            self.profile.secondary_rockfill_zone.boundary_points(),
        )

    def build_cushion_layer_brep(self) -> Any | None:
        Rhino = _require_rhino()
        if self.profile.cushion_layer is None:
            return None
        return self._build_section_brep(
            Rhino,
            self.profile.cushion_layer.boundary_points(),
        )

    def build_transition_layer_brep(self) -> Any | None:
        Rhino = _require_rhino()
        if self.profile.transition_layer is None:
            return None
        return self._build_section_brep(
            Rhino,
            self.profile.transition_layer.boundary_points(),
        )

    def build_primary_rockfill_brep(
        self,
        body_brep: Any,
        zone_breps: tuple[Any | None, ...],
    ) -> Any:
        subtraction_breps = tuple(brep for brep in zone_breps if brep is not None)
        if not subtraction_breps:
            return body_brep

        Rhino = _require_rhino()
        tolerance = _model_tolerance(Rhino)
        body = body_brep.DuplicateBrep() if hasattr(body_brep, "DuplicateBrep") else body_brep
        subtractors = tuple(
            brep.DuplicateBrep() if hasattr(brep, "DuplicateBrep") else brep
            for brep in subtraction_breps
        )
        difference = Rhino.Geometry.Brep.CreateBooleanDifference(
            [body],
            subtractors,
            tolerance,
        )
        if not difference:
            raise RuntimeError(
                "Failed to create primary rockfill Brep with Rhino boolean difference."
            )

        primary = difference[0]
        if primary is None or not primary.IsValid:
            raise RuntimeError("Primary rockfill Brep from boolean difference is invalid.")
        return primary

    def build_construction_stage_geometries(
        self,
        zone_breps: tuple[tuple[str, Any | None], ...],
    ) -> tuple[ConstructionStageGeometry, ...]:
        if not self.parameters.construction_stages:
            return ()

        Rhino = _require_rhino()
        stage_geometries: list[ConstructionStageGeometry] = []
        for stage in self.parameters.construction_stages:
            slab_brep = self._build_stage_slab_brep(Rhino, stage)
            parts: list[ConstructionStagePart] = []
            for zone_name, zone_brep in zone_breps:
                if zone_brep is None:
                    continue
                breps = self._intersect_zone_with_stage_slab(
                    zone_brep,
                    slab_brep,
                    zone_name,
                    stage,
                )
                if breps:
                    parts.append(ConstructionStagePart(zone_name=zone_name, breps=breps))
            if parts:
                stage_geometries.append(
                    ConstructionStageGeometry(stage=stage, parts=tuple(parts))
                )
        return tuple(stage_geometries)

    def build_terrain_constraint_brep(self) -> Any | None:
        Rhino = _require_rhino()
        if self.parameters.terrain_boundary is None:
            return None
        return self._build_terrain_constraint_brep(Rhino, self.parameters.terrain_boundary)

    def _build_section_brep(
        self,
        Rhino: Any,
        section_points: tuple[ProfilePoint, ...],
    ) -> Any:
        tolerance = _model_tolerance(Rhino)
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
        has_terrain_boundary = self.parameters.terrain_boundary is not None
        upstream, downstream, crest = (
            (None, (), None) if has_terrain_boundary else self.build_surfaces()
        )
        terrain_constraint = self.build_terrain_constraint_brep()
        body = self._clip_with_terrain_constraint(
            self.build_body_brep(),
            terrain_constraint,
            "body_brep",
        )
        secondary = self._clip_optional_with_terrain_constraint(
            self.build_secondary_rockfill_brep(),
            terrain_constraint,
            "secondary_rockfill_brep",
        )
        cushion = self._clip_optional_with_terrain_constraint(
            self.build_cushion_layer_brep(),
            terrain_constraint,
            "cushion_layer_brep",
        )
        transition = self._clip_optional_with_terrain_constraint(
            self.build_transition_layer_brep(),
            terrain_constraint,
            "transition_layer_brep",
        )
        primary = self.build_primary_rockfill_brep(
            body,
            (secondary, cushion, transition),
        )
        construction_stages = self.build_construction_stage_geometries(
            (
                ("primary_rockfill", primary),
                ("secondary_rockfill", secondary),
                ("cushion_layer", cushion),
                ("transition_layer", transition),
            )
        )
        return DamGeometry(
            profile_curve=None if has_terrain_boundary else self.build_profile_curve(),
            body_brep=body,
            primary_rockfill_brep=primary,
            secondary_rockfill_brep=secondary,
            cushion_layer_brep=cushion,
            transition_layer_brep=transition,
            secondary_rockfill_profile_curve=(
                None
                if has_terrain_boundary
                else self.build_secondary_rockfill_profile_curve()
            ),
            upstream_slope_surface=upstream,
            downstream_surfaces=downstream,
            crest_platform_surface=crest,
            construction_stages=construction_stages,
        )

    def add_to_document(self, doc: Any | None = None) -> dict[str, Any]:
        Rhino = _require_rhino()
        if doc is None:
            doc = Rhino.RhinoDoc.ActiveDoc
        if doc is None:
            raise RuntimeError("No active Rhino document is available.")

        geometry = self.build()
        object_ids = {
            "body_brep": doc.Objects.AddBrep(geometry.body_brep),
            "primary_rockfill_brep": doc.Objects.AddBrep(
                geometry.primary_rockfill_brep
            ),
        }
        if geometry.profile_curve is not None:
            object_ids["profile_curve"] = doc.Objects.AddCurve(geometry.profile_curve)
        if geometry.upstream_slope_surface is not None:
            object_ids["upstream_slope_surface"] = doc.Objects.AddBrep(
                geometry.upstream_slope_surface
            )
        if geometry.crest_platform_surface is not None:
            object_ids["crest_platform_surface"] = doc.Objects.AddBrep(
                geometry.crest_platform_surface
            )
        if geometry.secondary_rockfill_brep is not None:
            object_ids["secondary_rockfill_brep"] = doc.Objects.AddBrep(
                geometry.secondary_rockfill_brep
            )
        if geometry.cushion_layer_brep is not None:
            object_ids["cushion_layer_brep"] = doc.Objects.AddBrep(
                geometry.cushion_layer_brep
            )
        if geometry.transition_layer_brep is not None:
            object_ids["transition_layer_brep"] = doc.Objects.AddBrep(
                geometry.transition_layer_brep
            )
        if geometry.secondary_rockfill_profile_curve is not None:
            object_ids["secondary_rockfill_profile_curve"] = doc.Objects.AddCurve(
                geometry.secondary_rockfill_profile_curve
            )
        for index, downstream_surface in enumerate(geometry.downstream_surfaces):
            object_ids[f"downstream_surface_{index}"] = doc.Objects.AddBrep(
                downstream_surface
            )
        for stage_geometry in geometry.construction_stages:
            for part in stage_geometry.parts:
                object_ids.update(
                    self._add_stage_part_to_document(doc, stage_geometry.stage, part)
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

    def _build_terrain_constraint_brep(
        self,
        Rhino: Any,
        terrain_boundary: TerrainBoundary,
    ) -> Any:
        tolerance = _model_tolerance(Rhino)
        left_surface = self._build_terrain_loft_surface(
            Rhino,
            terrain_boundary.left_bank_contours,
            "left bank terrain surface",
        )
        right_surface = self._build_terrain_loft_surface(
            Rhino,
            terrain_boundary.right_bank_contours,
            "right bank terrain surface",
        )
        bottom_surface = self._build_loft_between_contours(
            Rhino,
            terrain_boundary.left_bank_contours[0],
            terrain_boundary.right_bank_contours[0],
            "bottom terrain boundary surface",
        )
        top_surface = self._build_loft_between_contours(
            Rhino,
            terrain_boundary.left_bank_contours[-1],
            terrain_boundary.right_bank_contours[-1],
            "top terrain boundary surface",
        )
        upstream_surface = self._build_cross_bank_surface(
            Rhino,
            terrain_boundary,
            0,
            "upstream terrain boundary surface",
        )
        downstream_surface = self._build_cross_bank_surface(
            Rhino,
            terrain_boundary,
            -1,
            "downstream terrain boundary surface",
        )

        joined = Rhino.Geometry.Brep.JoinBreps(
            [
                left_surface,
                right_surface,
                bottom_surface,
                top_surface,
                upstream_surface,
                downstream_surface,
            ],
            tolerance,
        )
        if not joined:
            raise RuntimeError("Failed to join terrain boundary surfaces into a Brep.")
        terrain_brep = joined[0]
        if terrain_brep is None or not terrain_brep.IsValid:
            raise RuntimeError("Terrain constraint Brep is invalid.")
        if hasattr(terrain_brep, "IsSolid") and not terrain_brep.IsSolid:
            raise RuntimeError("Terrain constraint Brep is not a closed solid.")
        return terrain_brep

    def _build_terrain_loft_surface(
        self,
        Rhino: Any,
        contours: tuple[TerrainContour, ...],
        label: str,
    ) -> Any:
        curves = [self._build_terrain_polyline_curve(Rhino, contour) for contour in contours]
        return self._create_single_loft_brep(Rhino, curves, label)

    def _build_loft_between_contours(
        self,
        Rhino: Any,
        first: TerrainContour,
        second: TerrainContour,
        label: str,
    ) -> Any:
        curves = [
            self._build_terrain_polyline_curve(Rhino, first),
            self._build_terrain_polyline_curve(Rhino, second),
        ]
        return self._create_single_loft_brep(Rhino, curves, label)

    def _build_cross_bank_surface(
        self,
        Rhino: Any,
        terrain_boundary: TerrainBoundary,
        point_index: int,
        label: str,
    ) -> Any:
        curves = []
        for left, right in zip(
            terrain_boundary.left_bank_contours,
            terrain_boundary.right_bank_contours,
        ):
            curves.append(
                Rhino.Geometry.PolylineCurve(
                    [
                        _to_point3d_tuple(Rhino, left.points[point_index]),
                        _to_point3d_tuple(Rhino, right.points[point_index]),
                    ]
                )
            )
        return self._create_single_loft_brep(Rhino, curves, label)

    def _create_single_loft_brep(
        self,
        Rhino: Any,
        curves: list[Any],
        label: str,
    ) -> Any:
        breps = Rhino.Geometry.Brep.CreateFromLoft(
            curves,
            Rhino.Geometry.Point3d.Unset,
            Rhino.Geometry.Point3d.Unset,
            Rhino.Geometry.LoftType.Normal,
            False,
        )
        if not breps:
            raise RuntimeError(f"Failed to create {label} from terrain contours.")
        brep = breps[0]
        if brep is None or not brep.IsValid:
            raise RuntimeError(f"{label} from terrain contours is invalid.")
        return brep

    def _build_terrain_polyline_curve(
        self,
        Rhino: Any,
        contour: TerrainContour,
    ) -> Any:
        return Rhino.Geometry.PolylineCurve(
            [_to_point3d_tuple(Rhino, point) for point in contour.points]
        )

    def _clip_optional_with_terrain_constraint(
        self,
        brep: Any | None,
        terrain_constraint: Any | None,
        label: str,
    ) -> Any | None:
        if brep is None:
            return None
        return self._clip_with_terrain_constraint(brep, terrain_constraint, label)

    def _clip_with_terrain_constraint(
        self,
        brep: Any,
        terrain_constraint: Any | None,
        label: str,
    ) -> Any:
        if terrain_constraint is None:
            return brep

        Rhino = _require_rhino()
        tolerance = _model_tolerance(Rhino)
        target = brep.DuplicateBrep() if hasattr(brep, "DuplicateBrep") else brep
        constraint = (
            terrain_constraint.DuplicateBrep()
            if hasattr(terrain_constraint, "DuplicateBrep")
            else terrain_constraint
        )
        intersections = Rhino.Geometry.Brep.CreateBooleanIntersection(
            [target],
            [constraint],
            tolerance,
        )
        if not intersections:
            raise RuntimeError(f"Terrain clipping produced no valid {label}.")
        clipped = intersections[0]
        if clipped is None or not clipped.IsValid:
            raise RuntimeError(f"Terrain-clipped {label} is invalid.")
        return clipped

    def _build_stage_slab_brep(
        self,
        Rhino: Any,
        stage: ConstructionStage,
    ) -> Any:
        x_min, x_max, y_min, y_max = self._stage_slab_plan_bounds()
        return self._build_box_brep(
            Rhino,
            x_min,
            x_max,
            y_min,
            y_max,
            stage.bottom_elevation,
            stage.top_elevation,
            f"construction stage {stage.stage_index} slab",
        )

    def _stage_slab_plan_bounds(self) -> tuple[float, float, float, float]:
        points: list[tuple[float, float, float]] = []
        points.extend(point.as_tuple() for point in self.profile.points())
        if self.profile.secondary_rockfill_zone is not None:
            points.extend(
                point.as_tuple()
                for point in self.profile.secondary_rockfill_zone.boundary_points()
            )
        if self.profile.cushion_layer is not None:
            points.extend(point.as_tuple() for point in self.profile.cushion_layer.points)
        if self.profile.transition_layer is not None:
            points.extend(point.as_tuple() for point in self.profile.transition_layer.points)
        if self.parameters.terrain_boundary is not None:
            for contour in (
                *self.parameters.terrain_boundary.left_bank_contours,
                *self.parameters.terrain_boundary.right_bank_contours,
            ):
                points.extend(contour.points)

        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(0.0, *y_values), max(self.parameters.axis_length, *y_values)
        x_padding = max((x_max - x_min) * 0.05, 10.0)
        y_padding = max((y_max - y_min) * 0.05, 10.0)
        return (
            x_min - x_padding,
            x_max + x_padding,
            y_min - y_padding,
            y_max + y_padding,
        )

    def _build_box_brep(
        self,
        Rhino: Any,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        z_min: float,
        z_max: float,
        label: str,
    ) -> Any:
        tolerance = _model_tolerance(Rhino)
        p000 = Rhino.Geometry.Point3d(x_min, y_min, z_min)
        p100 = Rhino.Geometry.Point3d(x_max, y_min, z_min)
        p110 = Rhino.Geometry.Point3d(x_max, y_max, z_min)
        p010 = Rhino.Geometry.Point3d(x_min, y_max, z_min)
        p001 = Rhino.Geometry.Point3d(x_min, y_min, z_max)
        p101 = Rhino.Geometry.Point3d(x_max, y_min, z_max)
        p111 = Rhino.Geometry.Point3d(x_max, y_max, z_max)
        p011 = Rhino.Geometry.Point3d(x_min, y_max, z_max)

        faces = (
            Rhino.Geometry.Brep.CreateFromCornerPoints(p000, p100, p110, p010, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(p001, p011, p111, p101, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(p000, p001, p101, p100, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(p100, p101, p111, p110, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(p110, p111, p011, p010, tolerance),
            Rhino.Geometry.Brep.CreateFromCornerPoints(p010, p011, p001, p000, tolerance),
        )
        if any(face is None or not face.IsValid for face in faces):
            raise RuntimeError(f"Failed to create valid faces for {label}.")

        joined = Rhino.Geometry.Brep.JoinBreps(faces, tolerance)
        if not joined:
            raise RuntimeError(f"Failed to join {label} into a Brep.")
        box_brep = joined[0]
        if box_brep is None or not box_brep.IsValid:
            raise RuntimeError(f"{label} Brep is invalid.")
        if hasattr(box_brep, "IsSolid") and not box_brep.IsSolid:
            raise RuntimeError(f"{label} Brep is not a closed solid.")
        return box_brep

    def _intersect_zone_with_stage_slab(
        self,
        zone_brep: Any,
        slab_brep: Any,
        zone_name: str,
        stage: ConstructionStage,
    ) -> tuple[Any, ...]:
        Rhino = _require_rhino()
        tolerance = _model_tolerance(Rhino)
        zone = zone_brep.DuplicateBrep() if hasattr(zone_brep, "DuplicateBrep") else zone_brep
        slab = slab_brep.DuplicateBrep() if hasattr(slab_brep, "DuplicateBrep") else slab_brep
        intersections = Rhino.Geometry.Brep.CreateBooleanIntersection(
            [zone],
            [slab],
            tolerance,
        )
        if not intersections:
            return ()

        valid_breps = tuple(brep for brep in intersections if brep is not None and brep.IsValid)
        if len(valid_breps) != len(intersections):
            raise RuntimeError(
                f"Construction stage {stage.stage_index} produced invalid {zone_name} Brep."
            )
        return valid_breps

    def _add_stage_part_to_document(
        self,
        doc: Any,
        stage: ConstructionStage,
        part: ConstructionStagePart,
    ) -> dict[str, Any]:
        object_ids: dict[str, Any] = {}
        base_name = _stage_part_name(stage, part.zone_name)
        for index, brep in enumerate(part.breps, start=1):
            name = base_name if len(part.breps) == 1 else f"{base_name}__part_{index:02d}"
            object_id = doc.Objects.AddBrep(brep)
            rhino_object = doc.Objects.FindId(object_id)
            if rhino_object is not None:
                rhino_object.Attributes.Name = name
                rhino_object.CommitChanges()
            object_ids[name] = object_id
        return object_ids


def _to_point3d(Rhino: Any, point: ProfilePoint) -> Any:
    return Rhino.Geometry.Point3d(point.x, point.y, point.z)


def _to_point3d_tuple(Rhino: Any, point: tuple[float, float, float]) -> Any:
    return Rhino.Geometry.Point3d(point[0], point[1], point[2])


def _stage_part_name(stage: ConstructionStage, zone_name: str) -> str:
    bottom = _format_elevation_for_name(stage.bottom_elevation)
    top = _format_elevation_for_name(stage.top_elevation)
    return f"stage_{stage.stage_index:02d}_{bottom}_{top}__{zone_name}"


def _format_elevation_for_name(elevation: float) -> str:
    text = f"{elevation:g}"
    return text.replace("-", "minus_").replace(".", "p")


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
