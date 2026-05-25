from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from export import ApdlMeshPackageOptions, export_apdl_mesh_package_from_rhino


MODEL_EXCHANGE_DIR = REPO_ROOT / "model_exchange"
DEFAULT_RHINO_MODELS_DIR = MODEL_EXCHANGE_DIR / "rhino_models"
DEFAULT_APDL_EXPORT_DIR = MODEL_EXCHANGE_DIR / "apdl_exports" / "apdl_job"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export named Rhino stage solids to SAT files and an APDL mesh macro."
    )
    parser.add_argument(
        "--input-3dm",
        default=None,
        help="Optional Rhino 3dm file to open before export. Defaults to the active document.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_APDL_EXPORT_DIR),
        help="Output directory for solids, manifest.json, import_and_mesh.mac, and report.",
    )
    parser.add_argument(
        "--rhino-models-dir",
        default=str(DEFAULT_RHINO_MODELS_DIR),
        help="Directory reserved for related Rhino source models.",
    )
    parser.add_argument(
        "--min-element-size",
        type=float,
        default=1.0,
        help="Minimum APDL ESIZE value in model units.",
    )
    parser.add_argument(
        "--elements-per-stage-height",
        type=float,
        default=2.0,
        help="Element count target through each construction layer height.",
    )
    args = parser.parse_args()

    options = ApdlMeshPackageOptions(
        min_element_size=args.min_element_size,
        elements_per_stage_height=args.elements_per_stage_height,
    )
    Path(args.rhino_models_dir).mkdir(parents=True, exist_ok=True)
    manifest = export_apdl_mesh_package_from_rhino(
        output_dir=args.output_dir,
        input_3dm=args.input_3dm,
        options=options,
    )
    print(f"Exported {len(manifest.records)} SAT solids.")
    print(f"Rhino model directory: {Path(args.rhino_models_dir).resolve()}")
    print(f"APDL mesh package: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
