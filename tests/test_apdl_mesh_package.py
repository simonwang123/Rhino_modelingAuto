from __future__ import annotations

import json

import pytest

from export import (
    ApdlMeshPackageOptions,
    build_apdl_stage_solid_record,
    load_apdl_mesh_package_manifest,
    parse_stage_solid_name,
    render_apdl_import_mesh_macro,
    write_apdl_mesh_package,
)
from export.apdl_mesh_package import _iter_rhino_objects


def test_parse_stage_solid_name_extracts_stage_elevations_and_zone() -> None:
    parsed = parse_stage_solid_name("stage_03_115_130__primary_rockfill")

    assert parsed is not None
    assert parsed.stage_index == 3
    assert parsed.bottom_elevation == pytest.approx(115.0)
    assert parsed.top_elevation == pytest.approx(130.0)
    assert parsed.zone_name == "primary_rockfill"


def test_parse_stage_solid_name_supports_decimal_and_negative_tokens() -> None:
    parsed = parse_stage_solid_name("stage_01_minus_5p5_0__cushion_layer")

    assert parsed is not None
    assert parsed.bottom_elevation == pytest.approx(-5.5)
    assert parsed.top_elevation == pytest.approx(0.0)


def test_parse_stage_solid_name_ignores_non_stage_names() -> None:
    assert parse_stage_solid_name("body_brep") is None
    assert parse_stage_solid_name("") is None


def test_stage_record_uses_default_material_map_and_safe_components() -> None:
    parsed = parse_stage_solid_name("stage_03_115_130__primary_rockfill")
    assert parsed is not None

    record = build_apdl_stage_solid_record(parsed, "solids/stage_03.sat")

    assert record.material_id == 1
    assert record.volume_component == "V_S03_Z115_Z130_PR"
    assert record.element_component == "E_S03_Z115_Z130_PR"
    assert len(record.volume_component) <= 32
    assert len(record.element_component) <= 32


def test_unknown_zone_requires_material_mapping() -> None:
    parsed = parse_stage_solid_name("stage_01_100_110__unknown_zone")
    assert parsed is not None

    with pytest.raises(ValueError, match="No material id"):
        build_apdl_stage_solid_record(parsed, "solids/unknown.sat")


def test_render_apdl_macro_imports_glues_assigns_and_meshes_new_elements() -> None:
    first = build_apdl_stage_solid_record(
        parse_stage_solid_name("stage_01_100_110__primary_rockfill"),
        "solids/stage_01_100_110__primary_rockfill.sat",
    )
    second = build_apdl_stage_solid_record(
        parse_stage_solid_name("stage_02_110_130__cushion_layer"),
        "solids/stage_02_110_130__cushion_layer.sat",
    )
    macro = render_apdl_import_mesh_macro(
        write_manifest_records(first, second),
        ApdlMeshPackageOptions(min_element_size=1.0, elements_per_stage_height=2.0),
    )

    assert "ET,1,SOLID185" in macro
    assert "MSHKEY,0" in macro
    assert "~SATIN,'stage_01_100_110__primary_rockfill','sat','solids',ALL,0" in macro
    assert "CM,V_S01_Z100_Z110_PR,VOLU" in macro
    assert "VATT,1,,1" in macro
    assert "VGLUE,ALL" in macro
    assert "ESIZE,5" in macro
    assert "ESIZE,10" in macro
    assert "*GET,EMAXBEF,ELEM,0,NUM,MAX" in macro
    assert "ESEL,S,ELEM,,ESTART,EMAXAFT" in macro
    assert "VMESH,ALL" in macro


def test_write_apdl_mesh_package_writes_manifest_macro_and_report(tmp_path) -> None:
    parsed = parse_stage_solid_name("stage_01_100_110__transition_layer")
    assert parsed is not None
    record = build_apdl_stage_solid_record(
        parsed,
        "solids/stage_01_100_110__transition_layer.sat",
    )

    manifest = write_apdl_mesh_package([record], tmp_path)

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "import_and_mesh.mac").exists()
    assert (tmp_path / "import_report.txt").exists()
    assert manifest.records == (record,)

    manifest_json = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_json["schema"] == "rhino_auto_modeling.apdl_mesh_package.v1"

    loaded = load_apdl_mesh_package_manifest(tmp_path / "manifest.json")
    assert loaded.records == (record,)


def test_iter_rhino_objects_prefers_get_object_list() -> None:
    first = object()
    second = object()

    class Objects:
        Count = 2

        def GetObjectList(self, settings=None):
            return (first, second)

        def __getitem__(self, index):
            raise IndexError

    objects = Objects()

    class Doc:
        Objects = objects

    assert _iter_rhino_objects(Doc()) == (first, second)


def write_manifest_records(*records):
    from export.apdl_mesh_package import ApdlMeshPackageManifest

    return ApdlMeshPackageManifest(records=records)
