"""Blender runtime fixtures: good pipe and deliberately broken variants, no private data."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def pipe(name, center):
    n = 64
    vertices = []
    for x, radius in ((-0.5, 0.1), (0.5, 0.1), (-0.5, 0.07), (0.5, 0.07)):
        vertices.extend((x, radius * math.cos(i * 2 * math.pi / n), radius * math.sin(i * 2 * math.pi / n)) for i in range(n))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend([(i, j, n + j, n + i), (2*n + i, 3*n + i, 3*n + j, 2*n + j),
                      (i, 2*n + i, 2*n + j, j), (n + i, n + j, 3*n + j, 3*n + i)])
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = center
    return obj


def build(directory, variant):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    pipe("Pipe_A", (0.5, 0, 1))
    pipe("Pipe_B", (1.5, 0, 1))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, 0, 0.45))
    support = bpy.context.object
    support.name = "Support"
    support.dimensions = (0.2, 0.3, 0.9)
    spec = {"schema_version": 1, "model_kind": "piping", "model": f"{variant}.blend", "objects": ["Pipe_*", "Support"],
            "dimensions": [{"objects": ["Pipe_*", "Support"], "expected_mm": [2000, 300, 1100], "tolerance_mm": 0.1}],
            "counts": [{"objects": ["Pipe_*"], "expected": 2}],
            "connected_parts": [{"object": "Pipe_A", "expected": 1}],
            "connections": [{"a": {"object": "Pipe_A", "point_m": [0.5, 0, 0], "axis": [1, 0, 0]},
                             "b": {"object": "Pipe_B", "point_m": [-0.5, 0, 0], "axis": [-1, 0, 0]}}],
            "contacts": [{"a": "Pipe_A", "b": "Support", "max_gap_mm": 0.1}],
            "collision_objects": ["Pipe_*", "Support"],
            "bore_paths": [{"objects": ["Pipe_*"], "points_m": [[-0.02, 0, 1], [2.02, 0, 1]], "sample_radius_m": 0.05}],
            "overview": {"objects": ["Pipe_*", "Support"]}, "required_views": ["overview", "detail"],
            "review_topics": ["Pipe bore and installation support", "whole-model overview"], "assumptions": ["Synthetic fixture only, no engineering rating"]}
    if variant == "bad_dimensions":
        spec["dimensions"][0]["expected_mm"][0] = 2100
    if variant == "detached_support":
        support.location.z -= 0.03
    if variant == "interference":
        support.location.z += 0.03
    if variant == "wrong_connection":
        bpy.data.objects["Pipe_B"].location.x += 0.05
    if variant == "blocked_bore":
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.065, depth=0.01, location=(0.6, 0, 1), rotation=(0, math.pi / 2, 0))
        bpy.context.object.name = "Blocker"
        spec["objects"].append("Blocker")
        spec["collision_objects"].append("Blocker")
        spec["bore_paths"][0]["objects"].append("Blocker")
    if variant == "contained_solid":
        bpy.ops.mesh.primitive_cube_add(size=0.05, location=(0.5, 0, 0.45))
        bpy.context.object.name = "Contained"
        spec["objects"].append("Contained")
        spec["collision_objects"].append("Contained")
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.region_3d.view_location = (1, 0, 0.55)
                space.region_3d.view_distance = 0.1 if variant == "closeup" else 12
                space.region_3d.view_perspective = "PERSP"
                space.clip_start, space.clip_end = 0.001, 100
    bpy.ops.object.camera_add(location=(3.7, -4, 3.2))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((1, 0, 0.55)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.2
    scene.camera = camera
    if variant == "good":
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 800, 500, 100
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "OBJECT"
        bpy.data.objects["Pipe_A"].color = (0.1, 0.45, 0.7, 1)
        bpy.data.objects["Pipe_B"].color = (0.1, 0.45, 0.7, 1)
        support.color = (0.4, 0.45, 0.5, 1)
        scene.render.filepath = str(directory / "overview.png")
        bpy.ops.render.render(write_still=True)
        camera.location = (2.6, -2, 1.7)
        camera.rotation_euler = (Vector((0.6, 0, 0.9)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = 1.5
        scene.render.filepath = str(directory / "detail.png")
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / f"{variant}.blend"))
    (directory / f"{variant}.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("Choose a new empty fixture directory")
    for variant in ["good", "bad_dimensions", "detached_support", "interference", "wrong_connection", "blocked_bore", "contained_solid", "closeup"]:
        build(directory, variant)


if __name__ == "__main__":
    main()
