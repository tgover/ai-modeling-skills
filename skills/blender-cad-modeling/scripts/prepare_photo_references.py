"""Run inside Blender: import a local image manifest without clearing an existing scene."""
import argparse
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
import local_photo_reference as photos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    outputs = [args.output.resolve(), args.report.resolve()]
    if outputs[0] == outputs[1] or any(path.exists() for path in outputs):
        raise FileExistsError("Choose distinct, new output and report paths")
    if outputs[0].suffix.lower() != ".blend":
        raise ValueError("Output must be a .blend file")
    manifest_file = args.manifest.resolve()
    if manifest_file in outputs:
        raise ValueError("Do not overwrite the input manifest")
    spec = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if spec.get("schema_version") != 1 or not isinstance(spec.get("references"), list) or not spec["references"]:
        raise ValueError("Expected schema_version=1 and a nonempty references list")
    for item in spec["references"]:
        image = (manifest_file.parent / item["file"]).resolve()
        obj = photos.load_reference(image, view=item.get("view", "FRONT"),
                                    location=item.get("location_scene_units", [0, 0, 0]))
        calibration = item.get("calibration")
        if calibration is not None:
            photos.calibrate(obj, calibration["point_a"], calibration["point_b"],
                             calibration["known_distance_mm"],
                             calibration.get("basis", "photo_planar_estimate"))
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(outputs[0]))
    photos.write_manifest(outputs[1])
    print(json.dumps({"blend": str(outputs[0]), "report": str(outputs[1]),
                      "geometry_generated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
