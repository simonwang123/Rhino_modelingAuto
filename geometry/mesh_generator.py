from __future__ import annotations

from typing import Any


class MeshGenerator:
    """Reserved extension point for finite-element mesh generation."""

    def generate(self, geometry: Any) -> Any:
        raise NotImplementedError("Mesh generation will be implemented in a later phase.")
