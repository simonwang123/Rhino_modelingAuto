from __future__ import annotations

from .dam_parameters import DamParameters


class KnowledgeDrivenModifier:
    """Reserved extension point for KG/LLM-driven parameter updates."""

    def modify(self, parameters: DamParameters) -> DamParameters:
        raise NotImplementedError(
            "Knowledge-driven parameter modification will be implemented in a later phase."
        )
