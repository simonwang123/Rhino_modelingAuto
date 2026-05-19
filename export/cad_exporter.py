from __future__ import annotations

from pathlib import Path
from typing import Any

from export.base_exporter import BaseExporter


class CADExporter(BaseExporter):
    """Placeholder for STEP, IGES, OBJ, and other CAD exports."""

    def export(self, geometry: Any, output_path: str | Path) -> Path:
        raise NotImplementedError("CAD export will be implemented in a later phase.")
