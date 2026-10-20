"""Verify a local converter with a synthetic DXF -> DWG -> DXF round trip."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "4")
import ezdxf

from cad_prep import convert_dwg, write_json
from run_blender import config, hidden_process


def check_libredwg(output):
    drawing = ezdxf.new("R2000", units=ezdxf.units.MM)
    model = drawing.modelspace()
    drawing.layers.new("Outline")
    drawing.layers.new("Openings")
    model.add_lwpolyline([(0, 0), (200, 0), (200, 120), (0, 120)], close=True, dxfattribs={"layer": "Outline"})
    for center in [(30, 30), (170, 30), (170, 90), (30, 90)]:
        model.add_circle(center, 12, dxfattribs={"layer": "Openings"})
    with tempfile.TemporaryDirectory(prefix="blender_dwg_check_") as temporary:
        stage = Path(temporary)
        source = stage / "test.dxf"
        drawing.saveas(source)
        dwg = stage / "test.dwg"
        result = subprocess.run([config()["dwg_writer"], "--as", "r2000", "-o", str(dwg), str(source)],
                                capture_output=True, timeout=30, **hidden_process())
        (output / "dwg_create.log").write_bytes(result.stdout + result.stderr)
        if result.returncode or not dwg.is_file():
            raise RuntimeError(f"Could not create test DWG. See {output / 'dwg_create.log'}")
        target = output / "synthetic_test.dwg"
        shutil.copyfile(dwg, target)
    result = convert_dwg(target, output / "roundtrip.dxf", backend="libredwg")
    doc = ezdxf.readfile(output / "roundtrip.dxf")
    outline = list(doc.modelspace().query("LWPOLYLINE"))
    holes = list(doc.modelspace().query("CIRCLE"))
    assert len(outline) == 1 and outline[0].closed and len(holes) == 4
    assert doc.units == ezdxf.units.MM
    assert set(tuple(p[:2]) for p in outline[0].get_points()) == {(0, 0), (200, 0), (200, 120), (0, 120)}
    assert all(h.dxf.radius == 12 and h.dxf.layer == "Openings" for h in holes)
    assert {tuple(h.dxf.center)[:2] for h in holes} == {(30, 30), (170, 30), (170, 90), (30, 90)}
    write_json(output / "validation.json", {"status": "passed", "dwg_roundtrip": True,
                                           "units_layers_dimensions_and_holes": True, **result})
    print("LibreDWG DWG -> DXF units/layers/geometry: passed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=["libredwg", "autocad"], default=config().get("preferred_dwg_backend", "autocad"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("Choose an empty output directory")
    if args.backend == "libredwg":
        check_libredwg(output)
        return
    with tempfile.TemporaryDirectory(prefix="blender_dwg_check_") as temporary:
        stage = Path(temporary)
        drawing = ezdxf.new("R2018", units=ezdxf.units.MM)
        drawing.modelspace().add_lwpolyline([(0, 0), (200, 0), (200, 120), (0, 120)], close=True)
        drawing.saveas(stage / "source.dxf")
        dwg = stage / "test.dwg"
        script = stage / "create.scr"
        script.write_text('(setvar "FILEDIA" 0)\n(setvar "CMDDIA" 0)\n'
                          f'(command "_.SAVEAS" "2018" "{dwg.as_posix()}")\n'
                          '(command "_.QUIT" "_N")\n', encoding="ascii")
        try:
            isolated = stage / "profile"
            isolated.mkdir()
            result = subprocess.run([config()["autocad_core"], "/isolate", "CodexBlender", str(isolated),
                                     "/i", str(stage / "source.dxf"), "/s", str(script)],
                                    capture_output=True, timeout=45, cwd=stage, **hidden_process())
            raw = result.stdout + result.stderr
        except subprocess.TimeoutExpired as exc:
            raw = (exc.stdout or b"") + (exc.stderr or b"")
            (output / "autocad_timeout.log").write_bytes(raw)
            write_json(output / "validation.json", {"status": "failed", "reason": "AutoCAD initialization/conversion timed out after 45 seconds"})
            raise RuntimeError(f"AutoCAD timed out. See {output / 'autocad_timeout.log'}") from exc
        log = raw.decode("utf-16-le", errors="replace") if raw.count(b"\x00") > len(raw) // 8 else raw.decode("utf-8", errors="replace")
        (output / "autocad_create.log").write_text(log, encoding="utf-8")
        if result.returncode or not dwg.is_file():
            raise RuntimeError(f"AutoCAD could not create test DWG (exit={result.returncode}). See {output / 'autocad_create.log'}")
        target_dwg = output / "synthetic_test.dwg"
        shutil.copyfile(dwg, target_dwg)
    result = convert_dwg(target_dwg, output / "roundtrip.dxf", backend="autocad")
    model = ezdxf.readfile(output / "roundtrip.dxf")
    outline = list(model.modelspace().query("LWPOLYLINE"))
    assert len(outline) == 1 and outline[0].closed
    points = list(outline[0].get_points("xy"))
    assert max(p[0] for p in points) == 200 and max(p[1] for p in points) == 120
    write_json(output / "validation.json", {"status": "passed", "dwg_roundtrip": True, **result})
    print("Local AutoCAD DWG -> DXF conversion: passed", flush=True)


if __name__ == "__main__":
    main()
