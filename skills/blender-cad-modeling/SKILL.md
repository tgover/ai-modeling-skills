---
name: blender-cad-modeling
description: "Create editable Blender models from CAD drawings (DWG/DXF/PDF) and reference images using local Blender. Use for dimensioned architectural, equipment, mechanical, or scene modeling, rendering, and mesh export. Do not use image generation as a substitute for measured CAD geometry."
---

# CAD 与参考图 Blender 建模

Use locally installed Blender through its background Python interface. This workflow needs no modeling API key, network service, or listening control server. The packaged setup is intended for Windows; other operating systems require adapting and verifying their executable paths.

## Set up a computer once

For a new computer or missing dependencies, read [setup](references/setup.md). Run `scripts/configure.py --check` with the host environment Python to check Blender and pinned dependencies. If configuration is missing, identify the installed Blender executable and run `configure.py --blender '<executable>'` with that Python. Read the generated JSON report for the configuration location and dependency issues.

Machine configuration lives outside the skill at `$CODEX_HOME/environments/blender-cad/config.json` (default `~/.codex/environments/blender-cad/config.json`). `BLENDER_CAD_CONFIG` can select a different file. Never commit that machine-specific configuration. `BLENDER_EXECUTABLE` and `BLENDER_CAD_PYTHON` can override executable paths. The current project, drawings, and outputs belong in the user's selected workspace, not in the skill installation folder. Do not infer them from the repository that distributes this skill.

Install the skill at user scope when it should be callable across projects. Installing it does not install Blender or transfer credentials. If it is not detected, start a new chat or restart the client.

## Interpret the inputs

- Inspect the actual drawings and reference images before modeling. Inventory views, revisions, dimensions, layers, blocks, external references, units, and missing information.
- Treat dimensioned drawings as the source for geometry. Use photos for appearance and undocumented detail; perspective alone does not establish real dimensions. Record assumptions and conflicts instead of silently inventing engineering dimensions.
- Establish drawing units, one known overall dimension, coordinate origin, floor/elevation convention, and intended output. Continue supported portions when only optional detail is missing. Ask about missing dimensions that materially determine the model.
- PDF or scanned drawings require the existing PDF skill and image inspection. Do not infer calibrated dimensions from page size alone.

## Prepare and model

Run host tools with the configured environment Python. The Blender embedded Python has a different version: do not add the host virtual environment to Blender's module search path.
The installed host dependencies are pinned in [requirements-lock.txt](references/requirements-lock.txt). The runner defaults to four render threads; use `--threads 0` for automatic selection when resources permit.

```powershell
& '<environment-python>' -X utf8 '<skill>/scripts/cad_prep.py' inspect '<drawing.dxf>' --output '<report.json>'
& '<environment-python>' -X utf8 '<skill>/scripts/cad_prep.py' prepare '<drawing.dxf>' --output '<geometry.json>' --unit mm --layers 'Outline' 'Openings'
& '<environment-python>' -X utf8 '<skill>/scripts/run_blender.py' --script '<model.py>' -- --geometry '<geometry.json>' --output '<output-directory>'
```

`prepare` creates a sampled linework reference, not a finished solid. It retains source coordinates and converts them to meters. Set an explicit origin when large survey coordinates would reduce Blender precision. Review its unsupported-entity and external-reference warnings; text, dimensions, hatches, and proxy solids are not silently interpreted as geometry. Unspecified DXF units require an explicit unit. Layer filtering keeps unrelated drawing sheets and annotations out of the model.

For DWG use `cad_prep.py convert '<source.dwg>' --output '<copy.dxf>'`. The default backend is LibreDWG, which must be installed and configured on each computer before DWG conversion. DXF/PDF/image work does not require it. The converter operates on a temporary copy and leaves the original intact. Review the conversion log, parser warnings, audit fixes, custom/proxy entities, and relevant external references before claiming drawing completeness. If a relevant object is lost or conversion fails, request a DXF export or use a verified alternative. Do not claim native DWG parsing by ezdxf or lossless conversion of arbitrary CAD content.

`--backend autocad` selects an independently installed AutoCAD Core Console. Do not assume it is available until configured and tested on this computer. Avoid changing the user's AutoCAD configuration as an incidental modeling step.

Write a task-specific Blender script using `bpy`, optionally importing `<skill>/scripts/blender_tools.py` for units, CAD curves, packed reference images, exports, and measured bounds. Keep editable parts in named collections, retain construction references separately, and preserve the source script and dimensional parameters. Keep geometry in meters internally, with millimeters displayed for mechanical work. Export STL in millimeters and GLB in meters.

Use `run_blender.py --blend '<existing.blend>'` for an existing file. Use `--use-preferences` only when that task requires the user's configured add-ons. Default background runs use factory preferences and disable automatic embedded script execution; they do not alter the user's startup scene or preferences. `--ui` opens a saved model in Blender when requested.

For Huaxi branded presentation imagery, read the user's Huaxi color references when available and follow their visual rules. If unavailable and needed for the output, obtain the brand specifications. Do not recolor an actual product/material merely because it belongs to a Huaxi project.

## Verify and deliver

- Compare key bounding dimensions, hole diameters and locations, levels, and counts against the drawing. Use section and orthographic views where hidden detail matters.
- Save a new `.blend`, reopen it, and check object counts, geometry, packed images, and relevant dimensions. Inspect a rendered preview visually.
- Export only requested mesh formats; verify scale and geometry after export. A mesh file is not an engineering STEP/BREP solid. If STEP or manufacturing precision is required, use an appropriate CAD kernel and verify that separate deliverable.
- Deliver the editable model, requested exports, preview, modeling source, and a concise list of assumptions or incomplete details. Distinguish measured geometry from inferred detail.

Run `scripts/selftest.py --output '<new-test-directory>'` to verify the local DXF → Blender → GLB/STL → render/reopen pipeline. This synthetic fixture checks the environment; it does not prove arbitrary drawings can be reconstructed automatically.

## Maintainer GitHub sync preference

The maintaining user requested on 2026-10-20 that updates to this modeling skill be synced promptly to [tgover/ai-modeling-skills](https://github.com/tgover/ai-modeling-skills). When maintaining this user's skill, after the appropriate checks, update its release copy, README and catalog, commit and push in the same task, then verify the remote commit and report its link. This is standing authorization for this user's repository maintenance; it does not authorize uploads by other users installing the skill. Preserve portable configuration handling and exclude machine settings, credentials, private drawings/models and task logs. If publication fails, retain local changes and report the unsynced state accurately.
