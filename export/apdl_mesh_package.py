from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import json
import re
from typing import Any, Iterable


_STAGE_SOLID_NAME_PATTERN = re.compile(
    r"^stage_(?P<stage_index>\d+)_"
    r"(?P<bottom>(?:minus_)?\d+(?:p\d+)?)_"
    r"(?P<top>(?:minus_)?\d+(?:p\d+)?)__"
    r"(?P<zone>[A-Za-z0-9_]+)$"
)

DEFAULT_ZONE_MATERIAL_IDS = {
    "primary_rockfill": 1,
    "secondary_rockfill": 2,
    "cushion_layer": 3,
    "transition_layer": 4,
}


@dataclass(frozen=True)
class ApdlMeshPackageOptions:
    """Options for generating APDL import and volume meshing files."""

    element_type: str = "SOLID185"
    min_element_size: float = 1.0
    elements_per_stage_height: float = 2.0
    glue_volumes: bool = True
    material_ids: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_ZONE_MATERIAL_IDS)
    )

    def __post_init__(self) -> None:
        if self.element_type != "SOLID185":
            raise ValueError("Only SOLID185 is supported by the APDL mesh package.")
        if self.min_element_size <= 0:
            raise ValueError("min_element_size must be positive.")
        if self.elements_per_stage_height <= 0:
            raise ValueError("elements_per_stage_height must be positive.")
        for zone_name, material_id in self.material_ids.items():
            if not zone_name:
                raise ValueError("material_ids zone names must be non-empty.")
            if material_id <= 0:
                raise ValueError("material_ids values must be positive.")


@dataclass(frozen=True)
class StageSolidName:
    source_name: str
    stage_index: int
    bottom_elevation: float
    top_elevation: float
    zone_name: str


@dataclass(frozen=True)
class ApdlStageSolidRecord:
    source_name: str
    stage_index: int
    bottom_elevation: float
    top_elevation: float
    zone_name: str
    material_id: int
    sat_path: str
    volume_component: str
    element_component: str

    @property
    def stage_height(self) -> float:
        return self.top_elevation - self.bottom_elevation

    def to_dict(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "stage_index": self.stage_index,
            "bottom_elevation": self.bottom_elevation,
            "top_elevation": self.top_elevation,
            "zone_name": self.zone_name,
            "material_id": self.material_id,
            "sat_path": self.sat_path,
            "volume_component": self.volume_component,
            "element_component": self.element_component,
        }

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ApdlStageSolidRecord":
        return cls(
            source_name=str(values["source_name"]),
            stage_index=int(values["stage_index"]),
            bottom_elevation=float(values["bottom_elevation"]),
            top_elevation=float(values["top_elevation"]),
            zone_name=str(values["zone_name"]),
            material_id=int(values["material_id"]),
            sat_path=str(values["sat_path"]),
            volume_component=str(values["volume_component"]),
            element_component=str(values["element_component"]),
        )


@dataclass(frozen=True)
class ApdlMeshPackageManifest:
    records: tuple[ApdlStageSolidRecord, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rhino_auto_modeling.apdl_mesh_package.v1",
            "records": [record.to_dict() for record in self.records],
        }

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ApdlMeshPackageManifest":
        return cls(
            records=tuple(
                ApdlStageSolidRecord.from_dict(record)
                for record in values.get("records", ())
                if isinstance(record, dict)
            )
        )


def parse_stage_solid_name(name: str) -> StageSolidName | None:
    """Parse a Rhino object name like stage_03_115_130__primary_rockfill."""

    match = _STAGE_SOLID_NAME_PATTERN.match(name.strip())
    if match is None:
        return None

    bottom = _parse_elevation_token(match.group("bottom"))
    top = _parse_elevation_token(match.group("top"))
    if top <= bottom:
        raise ValueError(f"Stage top elevation must exceed bottom elevation: {name!r}.")
    return StageSolidName(
        source_name=name.strip(),
        stage_index=int(match.group("stage_index")),
        bottom_elevation=bottom,
        top_elevation=top,
        zone_name=match.group("zone"),
    )


def build_apdl_stage_solid_record(
    parsed_name: StageSolidName,
    sat_path: str | Path,
    options: ApdlMeshPackageOptions | None = None,
) -> ApdlStageSolidRecord:
    if options is None:
        options = ApdlMeshPackageOptions()

    material_id = options.material_ids.get(parsed_name.zone_name)
    if material_id is None:
        raise ValueError(f"No material id is configured for zone {parsed_name.zone_name!r}.")

    component_base = _apdl_component_base_name(parsed_name)
    return ApdlStageSolidRecord(
        source_name=parsed_name.source_name,
        stage_index=parsed_name.stage_index,
        bottom_elevation=parsed_name.bottom_elevation,
        top_elevation=parsed_name.top_elevation,
        zone_name=parsed_name.zone_name,
        material_id=material_id,
        sat_path=_apdl_path(sat_path),
        volume_component=f"V_{component_base}",
        element_component=f"E_{component_base}",
    )


def write_apdl_mesh_package(
    records: Iterable[ApdlStageSolidRecord],
    output_dir: str | Path,
    options: ApdlMeshPackageOptions | None = None,
) -> ApdlMeshPackageManifest:
    """Write manifest, APDL import macro, and report files for SAT records."""

    if options is None:
        options = ApdlMeshPackageOptions()

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    manifest = ApdlMeshPackageManifest(records=tuple(_sorted_records(records)))
    _validate_unique_components(manifest.records)

    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )
    (output / "import_and_mesh.mac").write_text(
        render_apdl_import_mesh_macro(manifest, options),
        encoding="utf-8",
    )
    (output / "import_report.txt").write_text(
        render_import_report(manifest, options),
        encoding="utf-8",
    )
    return manifest


def load_apdl_mesh_package_manifest(path: str | Path) -> ApdlMeshPackageManifest:
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("APDL mesh package manifest must be a JSON object.")
    return ApdlMeshPackageManifest.from_dict(values)


def render_apdl_import_mesh_macro(
    manifest: ApdlMeshPackageManifest,
    options: ApdlMeshPackageOptions | None = None,
) -> str:
    if options is None:
        options = ApdlMeshPackageOptions()

    lines = [
        "/PREP7",
        "! Auto-generated by rhino_autoModeling.",
        "! Import SAT solids, glue interfaces, assign material ids, and mesh volumes.",
        "ET,1,SOLID185",
        "MSHKEY,0",
        "",
    ]

    for record in manifest.records:
        lines.extend(
            [
                f"! Import {record.source_name}",
                "*GET,VMAXBEF,VOLU,0,NUM,MAX",
                _render_satin_command(record.sat_path),
                "*GET,VMAXAFT,VOLU,0,NUM,MAX",
                "VSTART=VMAXBEF+1",
                "VSEL,S,VOLU,,VSTART,VMAXAFT",
                f"CM,{record.volume_component},VOLU",
                f"VATT,{record.material_id},,1",
                "ALLSEL,ALL",
                "",
            ]
        )

    if options.glue_volumes:
        lines.extend(["ALLSEL,ALL", "VGLUE,ALL", "ALLSEL,ALL", ""])

    for record in manifest.records:
        element_size = _stage_element_size(record, options)
        lines.extend(
            [
                f"! Mesh {record.source_name}",
                f"CMSEL,S,{record.volume_component}",
                f"VATT,{record.material_id},,1",
                f"ESIZE,{element_size:g}",
                "*GET,EMAXBEF,ELEM,0,NUM,MAX",
                "VMESH,ALL",
                "*GET,EMAXAFT,ELEM,0,NUM,MAX",
                "ESTART=EMAXBEF+1",
                "ESEL,S,ELEM,,ESTART,EMAXAFT",
                f"CM,{record.element_component},ELEM",
                "ALLSEL,ALL",
                "",
            ]
        )

    lines.extend(["FINISH", ""])
    return "\n".join(lines)


def render_import_report(
    manifest: ApdlMeshPackageManifest,
    options: ApdlMeshPackageOptions | None = None,
) -> str:
    if options is None:
        options = ApdlMeshPackageOptions()

    lines = [
        "APDL mesh package",
        f"records: {len(manifest.records)}",
        f"element_type: {options.element_type}",
        f"glue_volumes: {options.glue_volumes}",
        "",
        "solids:",
    ]
    for record in manifest.records:
        lines.append(
            "- "
            f"{record.source_name}: mat={record.material_id}, "
            f"esize={_stage_element_size(record, options):g}, "
            f"volume_component={record.volume_component}, "
            f"element_component={record.element_component}"
        )
    return "\n".join(lines) + "\n"


def export_apdl_mesh_package_from_rhino(
    output_dir: str | Path,
    input_3dm: str | Path | None = None,
    options: ApdlMeshPackageOptions | None = None,
) -> ApdlMeshPackageManifest:
    """Export named Rhino stage solids to SAT files and write APDL mesh macro.

    This function must run inside Rhino 8 CPython or another environment where
    RhinoCommon and Rhino command export are available.
    """

    if options is None:
        options = ApdlMeshPackageOptions()

    Rhino = _require_rhino()
    if input_3dm is not None:
        input_path = Path(input_3dm).resolve()
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        if not Rhino.RhinoApp.RunScript(f'_-Open "{input_path}" _Enter', False):
            raise RuntimeError(f"Rhino failed to open {input_path}.")

    doc = Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("No active Rhino document is available.")

    output = Path(output_dir).resolve()
    solids_dir = output / "solids"
    solids_dir.mkdir(parents=True, exist_ok=True)

    records: list[ApdlStageSolidRecord] = []
    skipped: list[str] = []
    for rhino_object in _iter_rhino_objects(doc):
        name = str(rhino_object.Attributes.Name or "").strip()
        parsed = parse_stage_solid_name(name) if name else None
        if parsed is None:
            skipped.append(name or "<unnamed>")
            continue

        geometry = rhino_object.Geometry
        if not _is_closed_brep(geometry):
            raise RuntimeError(f"Rhino object {name!r} is not a closed Brep solid.")

        sat_file = solids_dir / f"{_safe_file_stem(name)}.sat"
        _export_single_rhino_object_to_sat(Rhino, doc, rhino_object, sat_file)
        records.append(
            build_apdl_stage_solid_record(
                parsed,
                sat_file.relative_to(output),
                options,
            )
        )

    if not records:
        raise RuntimeError("No Rhino Brep objects matched stage_XX_bottom_top__zone names.")

    manifest = write_apdl_mesh_package(records, output, options)
    _append_skipped_objects_to_report(output / "import_report.txt", skipped)
    return manifest


def _parse_elevation_token(value: str) -> float:
    normalized = value.replace("minus_", "-").replace("p", ".")
    return float(normalized)


def _apdl_component_base_name(parsed_name: StageSolidName) -> str:
    stage = f"S{parsed_name.stage_index:02d}"
    bottom = _apdl_elevation_token(parsed_name.bottom_elevation)
    top = _apdl_elevation_token(parsed_name.top_elevation)
    zone = _zone_component_token(parsed_name.zone_name)
    base = f"{stage}_{bottom}_{top}_{zone}"
    return _limit_apdl_name(base, 30)


def _apdl_elevation_token(elevation: float) -> str:
    text = f"{elevation:g}".replace("-", "M").replace(".", "P")
    return f"Z{text}"


def _zone_component_token(zone_name: str) -> str:
    words = [word for word in zone_name.upper().split("_") if word]
    if len(words) == 1:
        return words[0][:8]
    return "".join(word[0] for word in words)


def _limit_apdl_name(name: str, max_length: int) -> str:
    if len(name) <= max_length:
        return name
    checksum = hashlib.sha1(name.encode("ascii")).hexdigest()[:4].upper()
    return f"{name[: max_length - 5]}_{checksum}"


def _render_satin_command(sat_path: str) -> str:
    path = Path(sat_path)
    extension = path.suffix.lstrip(".") or "sat"
    stem = path.stem
    directory = _apdl_path(path.parent)
    if directory == ".":
        directory = ""
    return f"~SATIN,'{stem}','{extension}','{directory}',ALL,0"


def _safe_file_stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())


def _apdl_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _sorted_records(
    records: Iterable[ApdlStageSolidRecord],
) -> tuple[ApdlStageSolidRecord, ...]:
    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.stage_index,
                record.bottom_elevation,
                record.top_elevation,
                record.zone_name,
                record.source_name,
            ),
        )
    )


def _validate_unique_components(records: tuple[ApdlStageSolidRecord, ...]) -> None:
    names = [record.volume_component for record in records]
    names.extend(record.element_component for record in records)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate APDL component names: {', '.join(duplicates)}.")


def _stage_element_size(
    record: ApdlStageSolidRecord,
    options: ApdlMeshPackageOptions,
) -> float:
    return max(options.min_element_size, record.stage_height / options.elements_per_stage_height)


def _require_rhino() -> Any:
    try:
        import Rhino  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "RhinoCommon is required. Run this function inside Rhino 8 CPython."
        ) from exc
    return Rhino


def _iter_rhino_objects(doc: Any) -> tuple[Any, ...]:
    objects = doc.Objects
    if hasattr(objects, "GetObjectList"):
        try:
            Rhino = _require_rhino()
            settings = Rhino.DocObjects.ObjectEnumeratorSettings()
            _set_object_enumerator_option(settings, "NormalObjects", True)
            _set_object_enumerator_option(settings, "LockedObjects", True)
            _set_object_enumerator_option(settings, "HiddenObjects", True)
            _set_object_enumerator_option(settings, "DeletedObjects", False)
            return tuple(objects.GetObjectList(settings))
        except Exception:
            pass

        try:
            return tuple(objects.GetObjectList())
        except Exception:
            pass

    try:
        return tuple(obj for obj in objects if obj is not None)
    except Exception:
        count = int(getattr(objects, "Count", 0))
        rhino_objects = []
        for index in range(count):
            try:
                rhino_object = objects[index]
            except IndexError:
                continue
            if rhino_object is not None:
                rhino_objects.append(rhino_object)
        return tuple(rhino_objects)


def _set_object_enumerator_option(
    settings: Any,
    option_name: str,
    value: bool,
) -> None:
    if hasattr(settings, option_name):
        setattr(settings, option_name, value)


def _is_closed_brep(geometry: Any) -> bool:
    return bool(
        geometry is not None
        and geometry.GetType().Name == "Brep"
        and getattr(geometry, "IsValid", False)
        and getattr(geometry, "IsSolid", False)
    )


def _export_single_rhino_object_to_sat(
    Rhino: Any,
    doc: Any,
    rhino_object: Any,
    sat_file: Path,
) -> None:
    if sat_file.exists():
        sat_file.unlink()

    doc.Objects.UnselectAll()
    rhino_object.Select(True)
    doc.Views.Redraw()
    command = f'_-Export "{sat_file}" _Enter'
    if not Rhino.RhinoApp.RunScript(command, False):
        raise RuntimeError(f"Rhino SAT export command failed for {rhino_object.Attributes.Name!r}.")
    if not sat_file.exists():
        raise RuntimeError(f"Rhino SAT export did not create {sat_file}.")
    rhino_object.Select(False)


def _append_skipped_objects_to_report(report_path: Path, skipped: list[str]) -> None:
    if not skipped:
        return
    with report_path.open("a", encoding="utf-8") as report:
        report.write("\nskipped Rhino objects:\n")
        for name in skipped:
            report.write(f"- {name}\n")
