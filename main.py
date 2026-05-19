from __future__ import annotations

from config import DEFAULT_DAM_PARAMETERS
from geometry.dam_geometry_builder import DamGeometryBuilder


def main() -> dict[str, object]:
    builder = DamGeometryBuilder(DEFAULT_DAM_PARAMETERS)
    object_ids = builder.add_to_document()
    print("Dam model created in Rhino document:")
    for name, object_id in object_ids.items():
        print(f"  {name}: {object_id}")
    return object_ids


if __name__ == "__main__":
    main()
