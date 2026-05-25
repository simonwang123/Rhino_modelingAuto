from __future__ import annotations

from pathlib import Path
from typing import Any

from export.base_exporter import BaseExporter
from export.apdl_mesh_package import (
    ApdlMeshPackageManifest,
    ApdlMeshPackageOptions,
    export_apdl_mesh_package_from_rhino,
)
from geometry import ApdlPreparationOptions, DamGeometryBuilder
from models import DamParameters


class APDLExporter(BaseExporter):
    """Exports ANSYS/APDL-ready staged Rhino geometry."""

    def __init__(self, options: ApdlPreparationOptions | None = None) -> None:
        self.options = options or ApdlPreparationOptions()

    def export(self, geometry: Any, output_path: str | Path) -> Path:
        if isinstance(geometry, DamParameters):
            builder = DamGeometryBuilder(geometry)
        elif isinstance(geometry, DamGeometryBuilder):
            builder = geometry
        elif hasattr(geometry, "export_apdl_stage_3dm"):
            builder = geometry
        else:
            raise TypeError(
                "APDLExporter.export expects DamParameters or DamGeometryBuilder."
            )
        return builder.export_apdl_stage_3dm(output_path, self.options)

    def export_mesh_package_from_rhino(
        self,
        output_dir: str | Path,
        input_3dm: str | Path | None = None,
        options: ApdlMeshPackageOptions | None = None,
    ) -> ApdlMeshPackageManifest:
        """Export named Rhino stage solids to SAT files plus an APDL mesh macro."""

        return export_apdl_mesh_package_from_rhino(output_dir, input_3dm, options)


def export_apdl_stage_3dm(
    parameters: DamParameters,
    output_path: str | Path,
    options: ApdlPreparationOptions | None = None,
) -> Path:
    """Build and write an APDL-ready staged 3dm from dam parameters."""

    return DamGeometryBuilder(parameters).export_apdl_stage_3dm(
        output_path,
        options or ApdlPreparationOptions(),
    )
