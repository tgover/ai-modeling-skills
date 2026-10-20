"""Blender side of the measured synthetic CAD pipeline test."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_tools import add_reference_image, export_meshes, import_cad_curves, measured_bounds, save_model, set_metric_scene


def material(name, color, metallic=0.0, roughness=0.35):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Roughness"].default_value = roughness
    return mat


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def verify_scene(directory):
    plate = bpy.data.objects["CAD plate | 200 x 120 x 20 mm"]
    bounds = measured_bounds([plate])
    for measured, expected in zip(bounds["dimensions_mm"], (200, 120, 20)):
        assert abs(measured - expected) < 0.002, (measured, expected)
    assert any(image.packed_file for image in bpy.data.images if image.name.startswith("reference")), "Reference image was not packed"
    assert len(bpy.data.collections["CAD reference"].objects) == 2
    import bmesh
    mesh = bmesh.new()
    mesh.from_mesh(plate.data)
    assert all(edge.is_manifold for edge in mesh.edges), "Plate is not a closed manifold"
    assert mesh.calc_volume() > 0, "Normals/volume incorrect"
    result = {"reopened": True, "bounds": bounds, "manifold": True, "volume_m3": mesh.calc_volume(),
              "packed_reference": True, "mesh_objects": sum(o.type == "MESH" for o in bpy.data.objects)}
    mesh.free()
    (directory / "blender_reopen.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def build(directory):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    set_metric_scene()
    geometry = json.loads((directory / "geometry.json").read_text(encoding="utf-8"))
    import_cad_curves(directory / "geometry.json")
    add_reference_image(directory / "reference.png", width_m=0.24, location=(0.10, 0.06, -0.002))

    contour = next(p for p in geometry["paths"] if p["layer"] == "Outline")
    assert contour["closed"] and len(contour["points_m"]) == 4
    ring = contour["points_m"]
    height = 0.020
    vertices = [(p[0], p[1], 0) for p in ring] + [(p[0], p[1], height) for p in ring]
    n = len(ring)
    faces = [tuple(reversed(range(n))), tuple(range(n, n * 2))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    mesh = bpy.data.meshes.new("DXF extruded profile")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    plate = bpy.data.objects.new("CAD plate | 200 x 120 x 20 mm", mesh)
    bpy.context.scene.collection.objects.link(plate)
    plate["height_mm"] = 20.0
    plate["hole_diameter_mm"] = 24.0
    plate["geometry_source"] = "Synthetic DXF environment test, not a user design"
    plate.data.materials.append(material("Satin aluminum", (0.25, 0.34, 0.40), metallic=0.75, roughness=0.29))
    holes = [p for p in geometry["paths"] if p["layer"] == "Openings"]
    assert len(holes) == 4
    for index, hole in enumerate(holes):
        points = hole["points_m"]
        lower = [min(p[i] for p in points) for i in range(3)]
        upper = [max(p[i] for p in points) for i in range(3)]
        radius = (upper[0] - lower[0]) / 2
        center = ((lower[0] + upper[0]) / 2, (lower[1] + upper[1]) / 2, height / 2)
        bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=radius, depth=height * 3, location=center)
        cutter = bpy.context.object
        modifier = plate.modifiers.new(f"DXF hole {index + 1}", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = cutter
        bpy.context.view_layer.objects.active = plate
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    # Ground, camera and lights are excluded from the selected-only mesh exports.
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0.10, 0.06, -0.001))
    ground = bpy.context.object
    ground.name = "Studio ground"
    ground.data.materials.append(material("Warm studio", (0.16, 0.17, 0.19), roughness=0.8))
    bpy.ops.object.camera_add(location=(0.40, -0.32, 0.36))
    camera = bpy.context.object
    aim(camera, (0.10, 0.06, 0.006))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 0.32
    scene = bpy.context.scene
    scene.camera = camera
    for name, location, energy, size in [
        ("Key", (0.05, -0.08, 0.35), 12, 0.28),
        ("Fill", (-0.25, 0.12, 0.18), 5, 0.20),
        ("Rim", (0.25, 0.32, 0.30), 18, 0.20),
    ]:
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy, light_data.shape, light_data.size = energy, "DISK", size
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        aim(light, (0.10, 0.06, 0.01))
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.3, 0.34, 0.4, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 640, 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "preview.png")
    scene.view_settings.view_transform = "AgX"
    bpy.context.view_layer.update()
    bounds = measured_bounds([plate])
    for measured, expected in zip(bounds["dimensions_mm"], (200, 120, 20)):
        assert abs(measured - expected) < 0.002, bounds
    export_meshes([plate], directory, "sample_plate")
    bpy.ops.object.select_all(action="DESELECT")
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_location = (0.10, 0.06, 0.01)
                area.spaces.active.region_3d.view_distance = 0.45
                area.spaces.active.clip_start = 0.0001
    save_model(directory / "sample_plate.blend")
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.verify:
        verify_scene(args.output.resolve())
    else:
        build(args.output.resolve())


if __name__ == "__main__":
    main()
