---
name: solidworks-cad-modeling
description: "Create editable SolidWorks parts and assemblies from dimensioned drawings and reference images using native features, VBA macros, and local COM automation on Windows. Use for SW/SolidWorks modeling, dimensions, rebuild checks, and SLDPRT/SLDASM/STEP delivery; not Blender rendering or a generic MCP tutorial."
---

# SolidWorks 图纸与参考图建模

Use installed desktop SolidWorks. Follow the user's software version; this workflow targets the SW2022 API baseline, with other releases verified on the actual computer. A macro-first workflow is sufficient; MCP is optional and must not become a prerequisite for creating a model.

## Establish inputs and environment

- Inspect actual drawings, images, views, units, revisions, tolerances, and required deliverables. Dimensioned drawings control geometry; photos guide appearance and require a known scale. Ask about missing dimensions that determine the geometry; state other assumptions.
- Determine whether the result is a part, multibody part, assembly, sheet-metal model, or drawing. Preserve that distinction: a fused solid is not an assembly, and a mesh import is not a native feature history.
- On a new computer, read [setup](references/setup.md). `scripts/sw_status.py` checks registration and attaches to an already-running application without starting one or changing documents. No successful connection means no claim of completed SW modeling.
- Keep macros, input drawings, reports, and outputs in the current project. Machine paths and private source files do not belong in the skill's GitHub folder.

## Plan native features and generate a macro

Read [modeling workflow](references/modeling.md) for version handling, feature selection, units, validation, and failure recovery. Use native sketches and features: extrude/cut, revolve, sweep, loft, fillets, patterns, sheet-metal operations, and assembly mates as appropriate to the actual part. Do not force every drawing into the bundled plate example.

Centralize dimensions, name meaningful features, and record a feature plan. Use meters and radians for API geometry, converting drawing dimensions explicitly. Prefer actual reference-plane objects or configured names over assuming an English UI. Fully constrain critical production sketches and retain meaningful dimensions; clearly label underconstrained demonstration geometry.

Provide inspectable VBA source (`.bas`) or a task-specific COM script. A `.bas` file is source code, not a runnable `.swp` project. The first time, create a macro in SolidWorks, paste the module source, verify its module/procedure names, and save it as `.swp`. Use the existing macro runner only after that file exists.

The bundled `scripts/generate_plate_macro.py` creates a simple four-hole plate source and parameter manifest without needing SW installed. It is an environment acceptance example, not general image-to-CAD reconstruction. The template checks for existing outputs, creates a new part, checks rebuild/body count/volume, and attempts native/STEP saves. Source generation does not prove compilation or geometry correctness.

## Execute and verify

- Prefer an already-open SolidWorks session at the same Windows user/elevation. `scripts/run_macro.py` runs an existing `.swp` through `RunMacro2`; it never starts a new application. Use it only for the user-requested modeling task and a reviewed macro.
- New-model tasks create new documents. Do not overwrite or close unrelated open work. Stop on a failed feature or rebuild, inspect the first failure, and correct it instead of continuing an invalid feature chain.
- API success is not model acceptance. Check the expected body/component count, key dimensions and hole locations, rebuild results, feature tree, and saved files. Check the macro's own report even if `RunMacro2` returns success.
- Reopen the saved SLDPRT/SLDASM and any requested exchange format, check geometry and assembly references, and inspect orthographic/isometric views. Read back STEP units and shape; an existing export file alone is insufficient.
- Deliver editable native files, requested exports, a preview, macro/source, parameter manifest, and a concise validation/assumption note. Distinguish generated source, successful API invocation, and validated native geometry.

## Validation status of this package

The source generator and diagnostic/error paths can be checked without SW. The initial publishing computer has no usable SolidWorks COM registration, so the bundled VBA sample has **not** been compiled or executed in a real SolidWorks session. On each target computer, run the acceptance procedure in `references/setup.md` before describing native model creation or STEP export as verified.
