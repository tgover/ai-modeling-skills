"""Blender-only helpers. Geometry is in meters; displayed mechanical dimensions are mm."""
import json
from pathlib import Path

import bpy
from mathutils import Vector


def set_metric_scene():
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "MILLIMETERS"


def new_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def import_cad_curves(geometry, name="CAD reference"):
    data = json.loads(Path(geometry).read_text(encoding="utf-8"))
    if data["unit"] != "m":
        raise ValueError("Prepared CAD geometry must be in meters.")
    collection = new_collection(name)
    grouped = {}
    for path in data["paths"]:
        grouped.setdefault(path["layer"], []).append(path)
    for layer, paths in grouped.items():
        curve = bpy.data.curves.new(layer, "CURVE")
        curve.dimensions = "3D"
        for path in paths:
            spline = curve.splines.new("POLY")
            spline.points.add(len(path["points_m"]) - 1)
            for point, coordinates in zip(spline.points, path["points_m"]):
                point.co = (*coordinates, 1)
            spline.use_cyclic_u = path["closed"]
        obj = bpy.data.objects.new(layer, curve)
        collection.objects.link(obj)
        obj.hide_render = True
        obj["source_drawing"] = data["source"]
    return collection


def add_reference_image(filename, width_m, location=(0, 0, 0), rotation=(0, 0, 0)):
    if width_m <= 0:
        raise ValueError("Reference width must be positive and calibrated.")
    image = bpy.data.images.load(str(Path(filename).resolve()), check_existing=True)
    if image.size[0] <= 0 or image.size[1] <= 0:
        raise RuntimeError(f"Reference image could not be decoded: {filename}")
    image.pack()
    obj = bpy.data.objects.new("Reference | " + Path(filename).stem, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    obj.empty_display_size = width_m * max(image.size) / image.size[0]
    obj.color[3] = 0.35
    obj.location = location
    obj.rotation_euler = rotation
    obj.hide_render = True
    return obj


def measured_bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    if not points:
        raise ValueError("No objects to measure.")
    lower = [min(p[i] for p in points) for i in range(3)]
    upper = [max(p[i] for p in points) for i in range(3)]
    return {"min_m": lower, "max_m": upper, "dimensions_mm": [(upper[i] - lower[i]) * 1000 for i in range(3)]}


def export_meshes(objects, directory, stem="model"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(directory / f"{stem}.glb"), export_format="GLB", use_selection=True, export_apply=True)
    bpy.ops.wm.stl_export(filepath=str(directory / f"{stem}.stl"), export_selected_objects=True,
                          global_scale=1000.0, use_scene_unit=False, apply_modifiers=True)


def save_model(filename):
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(filename))
