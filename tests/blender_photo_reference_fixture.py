"""Run in two independent Blender processes; outputs are synthetic skill tests only."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/blender-cad-modeling/assets"))
import local_photo_reference as photos


def deny_network(event, args):
    if event in {"socket.connect", "socket.bind", "subprocess.Popen"}:
        raise RuntimeError(f"Offline reference test disallows {event}")


sys.addaudithook(deny_network)


def expect_error(function):
    try:
        function()
    except (ValueError, FileNotFoundError):
        return
    raise AssertionError("Invalid input was accepted")


def image_file(path, width, height):
    image = bpy.data.images.new(path.stem, width=width, height=height)
    image.generated_color = (0.12, 0.5, 0.24, 1)
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def assert_references():
    refs = [obj for obj in bpy.context.scene.objects if obj.get(photos.TAG)]
    assert len(refs) == 2
    for obj in refs:
        report = photos.object_report(obj)
        assert report["packed"] and report["calibration"]["current_scale_valid"], report
        assert obj.hide_render and obj.type == "EMPTY"
        assert obj["geometry_status"].startswith("reference_image_only")
        point_a = report["calibration"]["point_a"]
        point_b = report["calibration"]["point_b"]
        actual = (photos.pixel_to_world(obj, point_a) - photos.pixel_to_world(obj, point_b)).length * 1000
        assert math.isclose(actual, report["calibration"]["known_distance_mm"], abs_tol=0.002)
        assert len(obj["source_sha256"]) == 64
        # Independent expected aspect ratio and axis mappings.
        image_width, image_height = obj.data.size
        a = photos.pixel_to_world(obj, (0, image_height))
        b = photos.pixel_to_world(obj, (image_width, image_height))
        c = photos.pixel_to_world(obj, (0, 0))
        expected_width = 3.2 if report["view"] == "FRONT" else 0.6
        expected_height = 1.6 if report["view"] == "FRONT" else 1.2
        assert math.isclose((b-a).length, expected_width, abs_tol=1e-5)
        assert math.isclose((c-a).length, expected_height, abs_tol=1e-5)
        assert (c-a).normalized().dot(Vector((0, 0, 1))) > 0.999
        axis = Vector((1, 0, 0)) if report["view"] == "FRONT" else Vector((0, 1, 0))
        assert (b-a).normalized().dot(axis) > 0.999
    sentinel = bpy.data.objects["Cube"]
    assert tuple(sentinel.location) == (3, 4, 5)
    assert tuple(sentinel.scale) == (2, 2, 2)
    assert sentinel["user_edit"] == "preserve this"
    assert len([obj for obj in bpy.context.scene.objects if obj.type == "MESH"]) == 1
    assert bpy.context.scene.unit_settings.system == "IMPERIAL"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--stage", choices=("create", "reopen"), required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = args.directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    photos.register()
    assert hasattr(bpy.types.Scene, "local_photo_settings")
    if args.stage == "create":
        if (output / "references.blend").exists():
            raise FileExistsError("Use a new test directory")
        bpy.context.scene.unit_settings.system = "IMPERIAL"
        image_file(output / "front.png", 1600, 800)
        image_file(output / "right.png", 600, 1200)
        sentinel = bpy.data.objects["Cube"]
        sentinel.location = (3, 4, 5)
        sentinel.scale = (2, 2, 2)
        sentinel["user_edit"] = "preserve this"
        assert bpy.ops.local_photo.import_images(directory=str(output), files=[{"name": "front.png"}]) == {"FINISHED"}
        front = bpy.context.active_object
        assert front["scale_basis"] == "uncalibrated_display_only"
        settings = bpy.context.scene.local_photo_settings
        settings.point_a, settings.point_b, settings.known_mm = (200, 200), (1200, 200), 2000
        assert bpy.ops.local_photo.calibrate() == {"FINISHED"}
        right = photos.load_reference(output / "right.png", "RIGHT")
        bpy.context.scene.unit_settings.scale_length = 0.001
        photos.calibrate(right, (300, 100), (300, 1100), 1000)
        assert photos.object_report(right)["calibration"]["current_scale_valid"]
        right_distance = (photos.pixel_to_world(right, (300, 100)) -
                          photos.pixel_to_world(right, (300, 1100))).length
        assert math.isclose(right_distance * photos.unit_scale() * 1000, 1000, abs_tol=0.01)
        bpy.context.scene.unit_settings.scale_length = 1
        photos.calibrate(right, (300, 100), (300, 1100), 1000)
        expect_error(lambda: photos.calibrate(front, (0, 0), (0, 0), 1))
        expect_error(lambda: photos.calibrate(front, (0, 0), (10, 0), math.nan))
        expect_error(lambda: photos.calibrate(front, (0, 0), (10, 0), -1))
        expect_error(lambda: photos.calibrate(front, (0, 0), (1601, 0), 1000))
        expect_error(lambda: photos.load_reference(output / "missing.png"))
        front.scale = (2, 1, 1)
        bpy.context.view_layer.update()
        expect_error(lambda: photos.calibrate(front, (0, 0), (1000, 0), 2000))
        front.scale = (2, 2, 2)
        bpy.context.view_layer.update()
        assert not photos.object_report(front)["calibration"]["current_scale_valid"]
        photos.calibrate(front, (200, 200), (1200, 200), 2000)
        assert_references()
        report = photos.write_manifest(output / "create.json")
        assert not report["geometry_generated"]
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "references.blend"))
        # The reopening process must rely on packed images, not on existing originals.
        (output / "front.png").rename(output / "front-original-unavailable.png")
        (output / "right.png").rename(output / "right-original-unavailable.png")
    else:
        assert Path(bpy.data.filepath) == output / "references.blend"
        assert not (output / "front.png").exists() and not (output / "right.png").exists()
        assert_references()
        photos.write_manifest(output / "reopen.json")
    photos.unregister()
    assert not hasattr(bpy.types.Scene, "local_photo_settings")
    (output / f"{args.stage}-passed.json").write_text(json.dumps({
        "stage": args.stage, "passed": True, "network_disabled": True,
        "blender_version": bpy.app.version_string, "synthetic_skill_test_only": True,
    }, indent=2), encoding="utf-8")
    print(f"LOCAL_PHOTO_REFERENCE_{args.stage.upper()}_PASSED")


if __name__ == "__main__":
    main()
