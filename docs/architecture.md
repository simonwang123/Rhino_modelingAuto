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

The 2D dam profile is calculated in the `X-Z` plane and the regular 3D body
extends from `Y=0` to `Y=axis_length`. Downstream benches are modeled as
horizontal segments on the downstream profile; each sloped segment keeps the
configured downstream slope ratio.

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

Terrain-constrained modeling is optional. When a terrain boundary is provided,
left-bank and right-bank contours control the dam abutment boundary along the
`Y` dam-axis direction. CAD/IGES terrain contours are imported into Rhino first,
then sampled from Rhino curves into parameter point lists. The finite contour
set is lofted into continuous left and right bank surfaces plus top, bottom,
upstream, and downstream closing surfaces. The resulting closed constraint Brep
is intersected with the dam body and each material zone before the primary
rockfill Brep is computed.

Construction fill stages are optional and are defined by explicit top
elevations. The foundation elevation is used as the first stage bottom, and the
last top elevation must equal the crest elevation. Stage geometry is organized
by construction stage first, with material-zone parts inside each stage. This
keeps the model aligned with staged construction analysis: ANSYS/APDL export can
activate `stage_03_120_130` as a construction step while still assigning
different materials to its primary rockfill, secondary rockfill, cushion, and
transition parts.

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
- `TerrainBoundary` stores sampled left and right bank contour point lists. Use
  `utils.rhino_curve_sampling.sample_curve_to_terrain_contour` inside Rhino to
  convert imported CAD/IGES curves into these parameters.
- `construction_stage_top_elevations` controls staged fill geometry. Rhino
  objects are named with the stage as the primary key, for example
  `stage_03_120_130__primary_rockfill`.
- `MeshGenerator` is reserved for finite-element mesh generation.
- `APDLExporter` is reserved for ANSYS/APDL command generation.
- `KnowledgeDrivenModifier` is reserved for rule-based or LLM-based parameter
  adjustment.
