---
name: solidworks-cad-modeling
description: "Create editable SolidWorks parts and assemblies from drawings and reference images using a configured SolidWorks MCP server, native COM automation, or VBA macros on Windows. Use for SW/SolidWorks modeling, dimensions, rebuild checks, and SLDPRT/SLDASM/STEP delivery; not Blender rendering."
---

# SolidWorks 图纸与参考图建模

Use installed desktop SolidWorks and the user's chosen version. When a local `solidworks` MCP server is configured, use its tools for supported native operations. Read [MCP workflow](references/mcp.md) for connection, upstream reference routing, units, and acceptance limits. Keep COM/scripts and macros available for operations beyond the tool surface or computers without MCP. The macro source retains an SW2022 API baseline; a basic MCP modeling/save/reopen/STEP round trip has been verified on SW2024 SP5.

## Establish inputs and environment

- Inspect actual drawings, images, views, units, revisions, tolerances, and required deliverables. Dimensioned drawings control geometry; photos guide appearance and require a known scale. Ask about missing dimensions that determine the geometry; state other assumptions.
- Determine whether the result is a part, multibody part, assembly, sheet-metal model, or drawing. Preserve that distinction: a fused solid is not an assembly, and a mesh import is not a native feature history.
- On a new computer, read [setup](references/setup.md). `scripts/sw_status.py` checks registration and attaches to an already-running application without starting one or changing documents. No successful connection means no claim of completed SW modeling.
- Keep macros, input drawings, reports, and outputs in the current project. Machine paths and private source files do not belong in the skill's GitHub folder.

## Plan and build native features

Read [modeling workflow](references/modeling.md) for version handling, feature selection, units, validation, and failure recovery. Use native sketches and features: extrude/cut, revolve, sweep, loft, fillets, patterns, sheet-metal operations, and assembly mates as appropriate to the actual part. Do not force every drawing into the bundled plate example.

### User's default modeling requirements

- Prefer editable native SW features and assembly operations: sketches, boss extrude, cut extrude, revolve, sweep, holes, patterns, and mates. MCP/COM/macros are execution methods; the saved model should retain the corresponding meaningful native feature history. Do not substitute imported or opaque bodies for native features merely because they are easier to generate.
- Model the actual manufacturing and assembly structure. An ordinary part must be a physically continuous solid; do not put unrelated disconnected or floating objects into one SLDPRT. Separate independent physical pieces into parts and assemble them in SLDASM. A legitimate weldment/multibody workflow must reflect real fabrication and connected structure, not serve as a container for scattered components.
- Reuse one master SLDPRT for identical geometry/specification/material, inserting multiple component instances or a native component pattern in the assembly. Do not recreate each identical item as another independent file or detached body within a part. Equal outer dimensions alone do not make different designs identical.
- Place components at their real installation interfaces and add appropriate coincident, concentric, distance, angle, or other mates. Fix the assembly's reference component and constrain the others according to design intent; preserve only intentional motion. Setting arbitrary component coordinates or fixing every component does not establish a valid assembly.
- Before delivery, check unexpected disconnected bodies, missing or failed mates, unintended component freedom, physical joints/supports, repeated-component references, and interference/clearance. Inspect the normal assembled state in multiple views; an exploded arrangement is only an explicitly requested additional presentation. A good-looking screenshot or a successful rebuild alone does not establish physical connectivity. Read [modeling workflow](references/modeling.md) for acceptance details.

Centralize dimensions, name meaningful features, and record a feature plan. Use meters and radians for API geometry, converting drawing dimensions explicitly. Prefer actual reference-plane objects or configured names over assuming an English UI. Fully constrain critical production sketches and retain meaningful dimensions; clearly label underconstrained demonstration geometry.

For MCP work, record the parameters, actual tool results, and validation evidence in the task project. Inspect the current tool schemas rather than assuming every upstream example is exposed over MCP. For a scripted operation, provide inspectable VBA source (`.bas`) or a task-specific COM script. A `.bas` file is source code, not a runnable `.swp` project. The first time, create a macro in SolidWorks, paste the module source, verify its module/procedure names, and save it as `.swp`. Use the existing macro runner only after that file exists.

The bundled `scripts/generate_plate_macro.py` creates a simple four-hole plate source and parameter manifest without needing SW installed. It is an environment acceptance example, not general image-to-CAD reconstruction. The template checks for existing outputs, creates a new part, checks rebuild/body count/volume, and attempts native/STEP saves. Source generation does not prove compilation or geometry correctness.

## Execute and verify

- Prefer an already-open SolidWorks session at the same Windows user/elevation. MCP's `solidworks_connect` can launch SW when needed for an authorized task; confirm its returned revision before modeling. `scripts/run_macro.py` runs an existing `.swp` through `RunMacro2`; it never starts a new application. Use it only for the user-requested modeling task and a reviewed macro.
- New-model tasks create new documents. Do not overwrite or close unrelated open work. Stop on a failed feature or rebuild, inspect the first failure, and correct it instead of continuing an invalid feature chain.
- API success is not model acceptance. Check the expected body/component count, key dimensions and hole locations, rebuild results, feature tree, and saved files. Check the macro's own report even if `RunMacro2` returns success.
- Reopen the saved SLDPRT/SLDASM and any requested exchange format, check geometry and assembly references, and inspect orthographic/isometric views. Read back STEP units and shape; an existing export file alone is insufficient.
- Deliver editable native files, requested exports, a preview, macro/source, parameter manifest, and a concise validation/assumption note. Distinguish generated source, successful API invocation, and validated native geometry.

## Validation status of this package

The source generator and diagnostic/error paths were checked separately. On 2026-10-20, the configured upstream MCP passed a real SW2024 SP5 acceptance: native 60 × 40 × 10 mm sketch/extrusion, one body, 24,000 mm³ volume, save/reopen with native features, STEP export/reimport with matching dimensions/volume, and four-view previews. This does not verify the bundled VBA sample, advanced features, assemblies, drawings, Motion, or Simulation on SW2024. Each new target computer still needs the relevant acceptance procedure in `references/setup.md`.

## Maintainer GitHub sync preference

The maintaining user requested on 2026-10-20 that updates to this modeling skill be synced promptly to [tgover/ai-modeling-skills](https://github.com/tgover/ai-modeling-skills). When maintaining this user's skill, after the appropriate checks, update its release copy, README and catalog, commit and push in the same task, then verify the remote commit and report its link. This is standing authorization for this user's repository maintenance; it does not authorize uploads by other users installing the skill. Preserve portable configuration handling and exclude machine settings, credentials, private drawings/models and task logs. If publication fails, retain local changes and report the unsynced state accurately.
