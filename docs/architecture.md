# Rhino Auto Modeling Architecture

## Goal

This project provides the first link in an automated earth-rock dam design
pipeline: design parameters are converted into Rhino geometry.

The first implementation targets a homogeneous trapezoidal dam body. It is not
yet a detailed engineering model with core walls, filters, drains, staged
construction, meshing, or numerical simulation.

## Coordinate Convention

- `X`: river cross-section direction
- `Y`: dam axis direction
- `Z`: elevation

The 2D dam profile is calculated in the `X-Z` plane and the 3D body extends
from `Y=0` to `Y=axis_length`.

## Module Responsibilities

- `models`: validated parameter data structures and future knowledge-driven
  modifiers.
- `geometry`: pure profile calculation, RhinoCommon geometry building, and
  future mesh generation.
- `config`: default design parameters for manual Rhino execution.
- `export`: future CAD and ANSYS/APDL exporters.
- `utils`: shared Rhino document helpers.
- `tests`: pure Python tests that do not require RhinoCommon.

## Extension Points

- `DamParameters` can be produced by a knowledge graph, LLM agent, Bayesian
  optimizer, or external design service.
- `DamGeometryBuilder` is the current Rhino geometry executor.
- `MeshGenerator` is reserved for finite-element mesh generation.
- `APDLExporter` is reserved for ANSYS/APDL command generation.
- `KnowledgeDrivenModifier` is reserved for rule-based or LLM-based parameter
  adjustment.
