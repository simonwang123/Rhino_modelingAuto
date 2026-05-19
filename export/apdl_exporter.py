from __future__ import annotations

from pathlib import Path
from typing import Any

from export.base_exporter import BaseExporter


class APDLExporter(BaseExporter):
    """Placeholder for future ANSYS/APDL model export."""

    def export(self, geometry: Any, output_path: str | Path) -> Path:
        raise NotImplementedError("APDL export will be implemented in a later phase.")
