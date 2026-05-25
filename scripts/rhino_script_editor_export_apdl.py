from __future__ import annotations

from pathlib import Path
import sys


# Edit these paths in Rhino's Python script editor when needed.
REPO_ROOT = Path(r"G:\rhino_autoModeling")
INPUT_3DM = REPO_ROOT / "model_exchange" / "rhino_models" / "apdl_stage_model.3dm"
OUTPUT_DIR = REPO_ROOT / "model_exchange" / "apdl_exports" / "apdl_job"
MIN_ELEMENT_SIZE = 0.5
ELEMENTS_PER_STAGE_HEIGHT = 2.0

# Set to None to export the currently open Rhino document instead of opening INPUT_3DM.
INPUT_3DM_TO_OPEN = INPUT_3DM


if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from export import ApdlMeshPackageOptions, export_apdl_mesh_package_from_rhino


def run_export() -> None:
    options = ApdlMeshPackageOptions(
        min_element_size=MIN_ELEMENT_SIZE,
        elements_per_stage_height=ELEMENTS_PER_STAGE_HEIGHT,
    )
    manifest = export_apdl_mesh_package_from_rhino(
        output_dir=OUTPUT_DIR,
        input_3dm=INPUT_3DM_TO_OPEN,
        options=options,
    )
    print("APDL mesh package export completed.")
    print("Exported SAT solids: {}".format(len(manifest.records)))
    print("Rhino model directory: {}".format(REPO_ROOT / "model_exchange" / "rhino_models"))
    print("APDL output directory: {}".format(OUTPUT_DIR))
    print("MAPDL command:")
    print("/CWD,'{}'".format(OUTPUT_DIR))
    print("/INPUT,'import_and_mesh','mac'")


run_export()
