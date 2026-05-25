# APDL Mesh Package Export

This workflow exports already staged and zoned Rhino Brep solids to SAT files,
then generates a Mechanical APDL macro that imports, glues, attributes, and
meshes the volumes.

## Rhino Object Naming

Only closed Brep solids whose object names match this pattern are exported:

```text
stage_XX_bottom_top__zone
```

Examples:

```text
stage_01_100_107__primary_rockfill
stage_03_115_130__secondary_rockfill
stage_08_172_180__transition_layer
```

Supported default zone material ids:

```text
primary_rockfill = 1
secondary_rockfill = 2
cushion_layer = 3
transition_layer = 4
```

Objects with missing or non-matching names are skipped and listed in
`import_report.txt`.

## Rhino Export

Put related Rhino source models under:

```text
G:\rhino_autoModeling\model_exchange\rhino_models
```

### Run From Rhino Python Script Editor

Open this file in Rhino's Python script editor and run it:

```text
G:\rhino_autoModeling\scripts\rhino_script_editor_export_apdl.py
```

Edit these variables at the top of the script if needed:

```python
INPUT_3DM = REPO_ROOT / "model_exchange" / "rhino_models" / "apdl_stage_model.3dm"
OUTPUT_DIR = REPO_ROOT / "model_exchange" / "apdl_exports" / "apdl_job"
MIN_ELEMENT_SIZE = 1.0
ELEMENTS_PER_STAGE_HEIGHT = 2.0
```

Set this line if you want to export the currently open Rhino document instead
of opening a specific `.3dm` first:

```python
INPUT_3DM_TO_OPEN = None
```

### Run From Rhino Command Line

Run the script inside Rhino 8 CPython:

```powershell
RunPythonScript "G:\rhino_autoModeling\scripts\export_apdl_mesh_package_from_rhino.py"
```

The default output directory is:

```text
G:\rhino_autoModeling\model_exchange\apdl_exports\apdl_job
```

To open a specific 3dm file before exporting:

```powershell
RunPythonScript "G:\rhino_autoModeling\scripts\export_apdl_mesh_package_from_rhino.py" --input-3dm "G:\rhino_autoModeling\model_exchange\rhino_models\apdl_stage_model.3dm"
```

Generated files:

```text
model_exchange/apdl_exports/apdl_job/solids/*.sat
model_exchange/apdl_exports/apdl_job/manifest.json
model_exchange/apdl_exports/apdl_job/import_and_mesh.mac
model_exchange/apdl_exports/apdl_job/import_report.txt
```

## MAPDL Import And Mesh

In Mechanical APDL, run:

```apdl
/CWD,'G:\rhino_autoModeling\model_exchange\apdl_exports\apdl_job'
/INPUT,'import_and_mesh','mac'
```

The macro:

- imports each SAT file with `~SATIN`
- creates volume components per stage and material zone
- assigns `SOLID185` and material ids
- executes `VGLUE,ALL`
- uses `MSHKEY,0` free meshing
- sets `ESIZE = max(min_element_size, stage_height / elements_per_stage_height)`
- meshes each stage-zone volume component with `VMESH`
- creates element components for later staging or result review
