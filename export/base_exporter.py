from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseExporter(ABC):
    """Base interface for future geometry and analysis exporters."""

    @abstractmethod
    def export(self, geometry: Any, output_path: str | Path) -> Path:
        raise NotImplementedError
