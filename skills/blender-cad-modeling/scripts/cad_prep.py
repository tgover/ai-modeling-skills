"""Inspect DXF, prepare sampled reference linework, or convert DWG using local tools."""
import argparse
from collections import Counter
import json
import io
import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "4")
import ezdxf
from ezdxf import bbox, disassemble, path as dxfpath, units

from run_blender import config, hidden_process

UNIT_CODES = {"mm": 4, "cm": 5, "m": 6, "in": 1, "ft": 2}


def write_json(destination, data):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def inspect_dxf(source):
    doc = ezdxf.readfile(source)
    model = doc.modelspace()
    try:
        extents = bbox.extents(model, fast=True)
        bounds = {"min": list(extents.extmin), "max": list(extents.extmax)} if extents.has_data else None
    except (ezdxf.DXFError, ValueError, TypeError) as exc:
        bounds = {"error": str(exc)}
    annotations = []
    for entity in model:
        kind = entity.dxftype()
        if kind in {"TEXT", "MTEXT", "DIMENSION"}:
            item = {"type": kind, "layer": entity.dxf.layer, "handle": entity.dxf.handle}
            if kind == "MTEXT":
                item["text"] = entity.plain_text()
            elif kind == "TEXT":
                item["text"] = entity.dxf.text
            else:
                item["text"] = entity.dxf.get("text", "")
                item["actual_measurement"] = entity.dxf.get("actual_measurement", None)
            annotations.append(item)
    audit = doc.audit()
    code = int(doc.units)
    return {
        "source": str(Path(source).resolve()), "dxf_version": doc.dxfversion,
        "units_code": code, "units_name": units.unit_name(code),
        "modelspace_entity_count": len(model), "entity_types": dict(Counter(e.dxftype() for e in model)),
        "layers": [{"name": layer.dxf.name, "off": layer.is_off(), "frozen": layer.is_frozen(),
                    "entity_count": sum(e.dxf.layer == layer.dxf.name for e in model)} for layer in doc.layers],
        "bounds_drawing_units": bounds, "annotations": annotations,
        "external_references": [{"name": block.name, "path": block.block.dxf.get("xref_path", "")}
                                for block in doc.blocks if block.block.is_xref],
        "audit_errors": len(audit.errors), "audit_fixes": len(audit.fixes),
    }


def prepare_dxf(source, output, unit=None, layers=None, tolerance_mm=0.1, origin=(0, 0, 0)):
    doc = ezdxf.readfile(source)
    code = UNIT_CODES[unit] if unit else int(doc.units)
    if not code:
        raise ValueError("DXF has no drawing units. Specify --unit after confirming a known dimension.")
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError("Curve tolerance must be positive and finite.")
    factor = units.conversion_factor(code, units.M)
    if len(origin) != 3 or not all(math.isfinite(float(v)) for v in origin):
        raise ValueError("Origin must have three finite drawing coordinates.")
    selected = set(layers or [])
    paths, skipped, failures = [], Counter(), []
    model = list(doc.modelspace())
    # Select INSERTs by insertion layer, and direct entities by entity layer.
    roots = [e for e in model if not selected or e.dxf.layer in selected]
    supported = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "HELIX"}
    for entity in disassemble.recursive_decompose(roots):
        kind = entity.dxftype()
        if kind not in supported:
            skipped[kind] += 1
            continue
        try:
            contour = dxfpath.make_path(entity)
            for subpath in contour.sub_paths():
                points = [[(float(p[i]) - origin[i]) * factor for i in range(3)]
                          for p in subpath.flattening(distance=tolerance_mm * 0.001 / factor, segments=8)]
                if len(points) < 2:
                    continue
                closed = bool(subpath.is_closed)
                if closed and max(abs(points[0][i] - points[-1][i]) for i in range(3)) < 1e-10:
                    points.pop()
                paths.append({"type": kind, "layer": entity.dxf.layer, "closed": closed, "points_m": points})
        except (ezdxf.DXFError, ValueError, TypeError, NotImplementedError) as exc:
            skipped[kind] += 1
            failures.append({"type": kind, "handle": entity.dxf.handle, "error": str(exc)})
    all_points = [point for item in paths for point in item["points_m"]]
    warnings = []
    if skipped:
        warnings.append("Some entities were not imported as paths; inspect the source drawing and skipped counts.")
    if any(block.block.is_xref for block in doc.blocks):
        warnings.append("External reference definitions are present. Resolve relevant XREFs before claiming completeness.")
    if not paths:
        warnings.append("No supported geometry paths were found for the selected layers.")
    result = {
        "source": str(Path(source).resolve()), "unit": "m", "source_units": units.unit_name(code),
        "units_overridden": unit is not None, "source_to_meters": factor,
        "origin_drawing_units": list(origin), "tolerance_mm": tolerance_mm,
        "selected_layers": sorted(selected), "paths": paths,
        "bounds_m": {"min": [min(p[i] for p in all_points) for i in range(3)],
                     "max": [max(p[i] for p in all_points) for i in range(3)]} if all_points else None,
        "skipped_entity_types": dict(skipped), "conversion_errors": failures, "warnings": warnings,
    }
    write_json(output, result)
    return result


def convert_dwg(source, output, timeout=120, backend=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source.suffix.lower() != ".dwg" or output.suffix.lower() != ".dxf":
        raise ValueError("Conversion requires a DWG source and a new DXF output.")
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing output: {output}")
    backend = backend or config().get("preferred_dwg_backend", "autocad")
    if backend == "autocad":
        return convert_dwg_autocad(source, output, timeout)
    if backend != "libredwg":
        raise ValueError(f"Unknown DWG conversion backend: {backend}")
    binary = Path(config()["dwg_converter"])
    if not binary.is_file():
        raise FileNotFoundError(binary)
    with tempfile.TemporaryDirectory(prefix="blender_dwg_") as temporary:
        stage = Path(temporary)
        staged_source, staged_output = stage / "source.dwg", stage / "output.dxf"
        shutil.copyfile(source, staged_source)
        timed_out = False
        try:
            completed = subprocess.run([str(binary), "-o", str(staged_output), str(staged_source)],
                                       capture_output=True, timeout=timeout, **hidden_process())
            raw = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw = (exc.stdout or b"") + (exc.stderr or b"")
        log_path = output.with_suffix(".conversion.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(raw.decode("utf-8", errors="replace"), encoding="utf-8")
        if timed_out:
            raise RuntimeError(f"LibreDWG conversion timed out. See {log_path}")
        if completed.returncode or not staged_output.is_file():
            raise RuntimeError(f"LibreDWG conversion failed (exit={completed.returncode}). See {log_path}")
        parser_log = io.StringIO()
        handler = logging.StreamHandler(parser_log)
        logger = logging.getLogger("ezdxf")
        logger.addHandler(handler)
        try:
            doc = ezdxf.readfile(staged_output)
            audit = doc.audit()
        finally:
            logger.removeHandler(handler)
        parser_warnings = parser_log.getvalue().strip().splitlines()
        if parser_warnings:
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write("\nDXF parser messages:\n" + parser_log.getvalue())
        if len(doc.modelspace()) == 0 or audit.errors:
            raise RuntimeError(f"Converted DXF is empty or has audit errors. See {log_path}")
        shutil.copyfile(staged_output, output)
    return {"output": str(output), "backend": "libredwg", "entities": len(doc.modelspace()),
            "audit_fixes": len(audit.fixes), "parser_warnings": parser_warnings, "log": str(log_path),
            "note": "Review conversion warnings, proxy/custom entities, XREFs and reference views before modeling."}


def convert_dwg_autocad(source, output, timeout=120):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source.suffix.lower() != ".dwg" or output.suffix.lower() != ".dxf":
        raise ValueError("Conversion requires a DWG source and a new DXF output.")
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing output: {output}")
    binary = Path(config()["autocad_core"])
    if not binary.is_file():
        raise FileNotFoundError(f"AutoCAD Core Console not found: {binary}")
    with tempfile.TemporaryDirectory(prefix="blender_cad_") as temporary:
        stage = Path(temporary)
        result_path = stage / "converted.dxf"
        script = stage / "convert.scr"
        # Keep script/output paths ASCII; subprocess arguments preserve the source's Unicode path.
        script.write_text('(setvar "FILEDIA" 0)\n(setvar "CMDDIA" 0)\n'
                          f'(command "_.DXFOUT" "{result_path.as_posix()}" "16")\n'
                          '(command "_.QUIT" "_N")\n', encoding="ascii")
        timed_out = False
        try:
            isolated = stage / "profile"
            isolated.mkdir()
            completed = subprocess.run([str(binary), "/isolate", "CodexBlender", str(isolated),
                                        "/i", str(source), "/s", str(script), "/readonly"],
                                       capture_output=True, timeout=timeout, cwd=source.parent, **hidden_process())
            raw = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw = (exc.stdout or b"") + (exc.stderr or b"")
        log = raw.decode("utf-16-le", errors="replace") if raw.count(b"\x00") > len(raw) // 8 else raw.decode("utf-8", errors="replace")
        log_path = output.with_suffix(".conversion.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log, encoding="utf-8")
        if timed_out:
            raise RuntimeError(f"AutoCAD conversion timed out after {timeout} seconds. See {log_path}")
        if completed.returncode or not result_path.is_file():
            raise RuntimeError(f"AutoCAD conversion failed (exit={completed.returncode}). See {log_path}")
        doc = ezdxf.readfile(result_path)
        if len(doc.modelspace()) == 0:
            raise RuntimeError(f"Converted drawing has empty modelspace. See {log_path}")
        shutil.copyfile(result_path, output)
    return {"output": str(output), "entities": len(doc.modelspace()), "log": str(log_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "prepare", "convert"):
        item = sub.add_parser(name)
        item.add_argument("source", type=Path)
        item.add_argument("--output", type=Path, required=name != "inspect")
        if name == "convert":
            item.add_argument("--backend", choices=["libredwg", "autocad"])
        if name == "prepare":
            item.add_argument("--unit", choices=UNIT_CODES)
            item.add_argument("--layers", nargs="+")
            item.add_argument("--tolerance-mm", type=float, default=0.1)
            item.add_argument("--origin", nargs=3, type=float, default=(0, 0, 0))
    args = parser.parse_args()
    if args.command == "inspect":
        result = inspect_dxf(args.source)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "prepare":
        result = prepare_dxf(args.source, args.output, args.unit, args.layers, args.tolerance_mm, args.origin)
        print(json.dumps({"output": str(args.output), "path_count": len(result["paths"]), "warnings": result["warnings"]}, ensure_ascii=False))
    else:
        print(json.dumps(convert_dwg(args.source, args.output, backend=args.backend), ensure_ascii=False))


if __name__ == "__main__":
    main()
