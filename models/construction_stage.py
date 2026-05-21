from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstructionStage:
    """One construction fill stage bounded by bottom and top elevations."""

    stage_index: int
    bottom_elevation: float
    top_elevation: float

    def __post_init__(self) -> None:
        if self.stage_index <= 0:
            raise ValueError("stage_index must be positive.")
        if self.top_elevation <= self.bottom_elevation:
            raise ValueError("top_elevation must be greater than bottom_elevation.")
