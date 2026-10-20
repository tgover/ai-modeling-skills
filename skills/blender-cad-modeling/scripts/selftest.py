"""Exercise DXF units/curves, Blender build/render/reopen, GLB scale, and STL integrity."""
import argparse
import importlib.metadata
import json
import math
import os
import shutil
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "4")
from run_blender import config, hidden_process


def fixture(directory):
    import ezdxf
    from PIL import Image, ImageDraw
    import pymupdf
    drawing = ezdxf.new("R2018", units=ezdxf.units.MM)
    model = drawing.modelspace()
    for name in ("Outline", "Openings", "ReadChecks", "Annotations"):
        drawing.layers.new(name)
    model.add_lwpolyline([(0, 0), (200, 0), (200, 120), (0, 120)], close=True, dxfattribs={"layer": "Outline"})
    for center in ((30, 30), (170, 30), (170, 90), (30, 90)):
        model.add_circle(center, 12, dxfattribs={"layer": "Openings"})
    model.add_text("200 x 120 x 20 mm; 4 holes diameter 24", dxfattribs={"height": 4, "layer": "Annotations"})
    model.add_line((220, 0), (240, 20), dxfattribs={"layer": "ReadChecks"})
    model.add_arc((250, 50), 10, 10, 220, dxfattribs={"layer": "ReadChecks"})
    model.add_ellipse((250, 80), major_axis=(20, 0, 0), ratio=0.5, dxfattribs={"layer": "ReadChecks"})
    model.add_spline([(220, 100), (235, 118), (260, 100)], dxfattribs={"layer": "ReadChecks"})
    block = drawing.blocks.new("test_block")
    block.add_line((0, 0), (10, 10))
    model.add_blockref("test_block", (240, 130), dxfattribs={"layer": "ReadChecks"})
    drawing.saveas(directory / "sample.dxf")
    image = Image.new("RGB", (960, 640), "white")
    pen = ImageDraw.Draw(image)
    pen.rectangle((80, 100, 880, 580), outline=(36, 52, 61), width=5)
    for x, y in ((200, 220), (760, 220), (760, 460), (200, 460)):
        pen.ellipse((x - 48, y - 48, x + 48, y + 48), outline=(36, 52, 61), width=5)
    pen.text((80, 45), "SYNTHETIC CAD TEST | 200 x 120 x 20 mm | 4 x diameter 24 mm", fill=(36, 52, 61))
    image.save(directory / "reference.png")
    pdf = pymupdf.open()
    page = pdf.new_page(width=600, height=400)
    page.insert_text((50, 50), "CAD environment test: 200 x 120 x 20 mm", fontsize=14)
    pdf.save(directory / "sample.pdf")
    pdf.close()
    with pymupdf.open(directory / "sample.pdf") as loaded:
        assert "200 x 120 x 20" in loaded[0].get_text()
        loaded[0].get_pixmap().save(directory / "pdf_read_check.png")


def run_blender(directory, verify=False):
    scripts = Path(__file__).resolve().parent
    command = [sys.executable, "-X", "utf8", str(scripts / "run_blender.py")]
    if verify:
        command += ["--blend", str(directory / "sample_plate.blend")]
    command += ["--script", str(scripts / "smoke_scene.py"), "--", "--output", str(directory)]
    if verify:
        command.append("--verify")
    log = directory / ("blender_reopen.log" if verify else "blender_build.log")
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=300, **hidden_process())


def prepare_test(directory):
    import ezdxf
    import numpy as np
    from cad_prep import inspect_dxf, prepare_dxf, write_json
    fixture(directory)
    report = inspect_dxf(directory / "sample.dxf")
    assert report["units_code"] == 4 and report["audit_errors"] == 0
    write_json(directory / "cad_inspection.json", report)
    geometry = prepare_dxf(directory / "sample.dxf", directory / "geometry.json", layers=["Outline", "Openings"])
    assert len(geometry["paths"]) == 5 and not geometry["warnings"]
    np.testing.assert_allclose(geometry["bounds_m"]["max"], [0.2, 0.12, 0], atol=1e-9)
    all_geometry = prepare_dxf(directory / "sample.dxf", directory / "all_geometry.json")
    assert len(all_geometry["paths"]) == 10, len(all_geometry["paths"])
    assert all_geometry["skipped_entity_types"] == {"TEXT": 1}
    unitless = ezdxf.new("R2018", units=0)
    unitless.modelspace().add_line((10000, 20000), (11000, 20000))
    unitless.saveas(directory / "unitless.dxf")
    try:
        prepare_dxf(directory / "unitless.dxf", directory / "unitless_geometry.json")
    except ValueError as exc:
        assert "no drawing units" in str(exc)
    else:
        raise AssertionError("Unitless input was silently accepted")
    normalized = prepare_dxf(directory / "unitless.dxf", directory / "unitless_geometry.json", unit="mm", origin=(10000, 20000, 0))
    np.testing.assert_allclose(normalized["bounds_m"]["min"], [0, 0, 0])
    np.testing.assert_allclose(normalized["bounds_m"]["max"], [1, 0, 0])
    print("CAD units, line/arc/ellipse/spline/block paths, PDF and reference image: passed", flush=True)
    scripts = Path(__file__).resolve().parent
    shutil.copyfile(scripts / "smoke_scene.py", directory / "build_sample.py")
    shutil.copyfile(scripts / "blender_tools.py", directory / "blender_tools.py")


def validate_test(directory):
    import numpy as np
    from PIL import Image
    import trimesh
    from cad_prep import write_json
    glb = trimesh.load_scene(directory / "sample_plate.glb").to_mesh()
    stl = trimesh.load_mesh(directory / "sample_plate.stl")
    # GLB is Y-up, so compare sorted dimensions rather than assuming CAD axes.
    np.testing.assert_allclose(sorted(glb.extents), sorted([0.2, 0.12, 0.02]), atol=1e-6)
    np.testing.assert_allclose(stl.extents, [200, 120, 20], atol=0.002)
    assert stl.is_watertight and stl.volume > 0
    expected_volume_mm3 = (200 * 120 - 4 * math.pi * 12 ** 2) * 20
    assert abs(stl.volume - expected_volume_mm3) / expected_volume_mm3 < 0.001
    # Confirm the four nominal hole centers are open through the complete thickness.
    for x, y in ((30, 30), (170, 30), (170, 90), (30, 90)):
        projected = stl.triangles[:, :, :2]
        a, b, c = projected[:, 0], projected[:, 1], projected[:, 2]
        edge1, edge2, delta = b - a, c - a, np.array([x, y]) - a
        cross = lambda p, q: p[:, 0] * q[:, 1] - p[:, 1] * q[:, 0]
        determinant = cross(edge1, edge2)
        nonvertical = np.abs(determinant) > 1e-8
        u = cross(delta, edge2)[nonvertical] / determinant[nonvertical]
        v = cross(edge1, delta)[nonvertical] / determinant[nonvertical]
        blocked = (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8)
        assert not np.any(blocked), f"Unexpected face at hole center {(x, y)}"
    image = np.asarray(Image.open(directory / "preview.png").convert("RGB"))
    assert image.shape == (480, 640, 3) and image.std() > 10
    result = {
        "status": "passed", "synthetic_test": True, "environment": config(),
        "checks": {"dxf_units_and_layers": True, "curves_and_blocks": True,
                   "unitless_rejected": True, "origin_and_scale": True, "pdf_read_and_render": True,
                   "blender_build_and_reopen": True, "reference_packed": True,
                   "render": True, "glb_meters": True, "stl_millimeters": True,
                   "watertight": True, "four_holes_open": True, "volume": True},
        "stl_dimensions_mm": stl.extents.tolist(), "volume_mm3": float(stl.volume),
        "expected_volume_mm3": expected_volume_mm3,
        "packages": {p: importlib.metadata.version(p) for p in ("ezdxf", "Pillow", "PyMuPDF", "numpy", "trimesh", "PyYAML")},
    }
    write_json(directory / "validation.json", result)
    print(json.dumps({"status": result["status"], "report": str(directory / "validation.json")}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["prepare", "validate"])
    args = parser.parse_args()
    directory = args.output.resolve()
    if args.phase == "prepare":
        prepare_test(directory)
        return
    if args.phase == "validate":
        validate_test(directory)
        return
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        parser.error("Choose a new empty output directory to preserve previous test results.")
    # Release heavy host libraries before launching Blender on memory-constrained systems.
    subprocess.run([sys.executable, "-X", "utf8", __file__, "--output", str(directory), "--phase", "prepare"], check=True, **hidden_process())
    run_blender(directory)
    print("Blender model, exports and CPU render: created", flush=True)
    run_blender(directory, verify=True)
    subprocess.run([sys.executable, "-X", "utf8", __file__, "--output", str(directory), "--phase", "validate"], check=True, **hidden_process())


if __name__ == "__main__":
    main()
