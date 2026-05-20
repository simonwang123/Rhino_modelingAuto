# Rhino Auto Modeling Architecture

## Goal

This project provides the first link in an automated earth-rock dam design
pipeline: design parameters are converted into Rhino geometry.

The first implementation targets the outer geometry of an earth-rock dam body.
It supports downstream benches and primary/secondary rockfill zoning for
concrete face rockfill dam layout studies, but it is not yet a detailed
engineering model with face slabs, toe slabs, filters, drains, staged
construction, meshing, or numerical simulation.

## Coordinate Convention

- `X`: river cross-section direction
- `Y`: dam axis direction
- `Z`: elevation

The 2D dam profile is calculated in the `X-Z` plane and the 3D body extends
from `Y=0` to `Y=axis_length`. Downstream benches are modeled as horizontal
segments on the downstream profile; each sloped segment keeps the configured
downstream slope ratio.

Secondary rockfill zones are defined by four user-provided `(x, z)` section
points. The zone is validated in the section plane, extruded along the dam axis,
and subtracted from the total body to form a primary rockfill body for later
material assignment and meshing. If the two downstream-side control points lie
on the downstream boundary, the actual zone boundary follows the downstream
profile polyline, including bench corners; otherwise the downstream-side edge is
kept as a straight line that must remain inside the dam section.

Upstream cushion and transition layers are calculated automatically from top and
bottom horizontal thicknesses. The cushion layer is adjacent to the upstream dam
slope, and the transition layer is adjacent to the cushion layer on the dam-body
side. Both layers extend from the crest elevation to the foundation elevation,
are extruded along the dam axis, and are subtracted from the primary rockfill
body.

## Module Responsibilities

- `models`: validated parameter data structures and future knowledge-driven
  modifiers.
- `geometry`: pure profile calculation, RhinoCommon geometry building, and
  future mesh generation. Section polygon helpers keep rockfill-zone validation
  independent from RhinoCommon.
- `config`: default design parameters for manual Rhino execution.
- `export`: future CAD and ANSYS/APDL exporters.
- `utils`: shared Rhino document helpers.
- `tests`: pure Python tests that do not require RhinoCommon.

## Extension Points

- `DamParameters` can be produced by a knowledge graph, LLM agent, Bayesian
  optimizer, or external design service.
- `DamGeometryBuilder` is the current Rhino geometry executor.
- Primary rockfill, secondary rockfill, cushion layer, and transition layer
  Breps are separated so later finite-element workflows can assign materials and
  meshes by zone.
- `MeshGenerator` is reserved for finite-element mesh generation.
- `APDLExporter` is reserved for ANSYS/APDL command generation.
- `KnowledgeDrivenModifier` is reserved for rule-based or LLM-based parameter
  adjustment.
