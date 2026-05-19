from __future__ import annotations

from typing import Any


def get_active_doc() -> Any:
    try:
        import Rhino  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "RhinoCommon is required to access the active Rhino document."
        ) from exc

    doc = Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("No active Rhino document is available.")
    return doc
