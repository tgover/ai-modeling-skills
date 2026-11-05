"""Local image references for Blender; no network calls or third-party packages."""
bl_info = {
    "name": "Local Photo Reference / 本地参考图",
    "author": "AI Modeling Skills",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > 本地参考图",
    "description": "Import packed reference images and record planar scale evidence locally",
    "category": "Import-Export",
}

import hashlib
import json
import math
from pathlib import Path

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from mathutils import Vector

TAG = "local_photo_reference"
ROTATIONS = {
    "FRONT": (90, 0, 0), "BACK": (90, 0, 180),
    "RIGHT": (90, 0, 90), "LEFT": (90, 0, -90),
    "TOP": (0, 0, 0), "BOTTOM": (180, 0, 0), "DETAIL": (90, 0, 0),
}
VIEWS = [(key, label, "") for key, label in (
    ("FRONT", "前视"), ("BACK", "后视"), ("RIGHT", "右视"), ("LEFT", "左视"),
    ("TOP", "顶视"), ("BOTTOM", "底视"), ("DETAIL", "透视 / 局部照片"))]


def unit_scale():
    value = bpy.context.scene.unit_settings.scale_length
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Scene unit scale must be finite and positive")
    return value


def reference_collection():
    for collection in bpy.context.scene.collection.children:
        if collection.get(TAG):
            return collection
    collection = bpy.data.collections.new("References | Local Photos")
    collection[TAG] = True
    bpy.context.scene.collection.children.link(collection)
    return collection


def set_display_size(obj, desired):
    if not math.isfinite(desired) or desired <= 0:
        raise ValueError("Reference display size must be finite and positive")
    prop = obj.bl_rna.properties["empty_display_size"]
    bounded = min(prop.hard_max, max(prop.hard_min, desired))
    obj.empty_display_size = bounded
    # Blender limits Empty display size; preserve physical scale in small scene units.
    obj.scale *= desired / obj.empty_display_size


def load_reference(filename, view="FRONT", location=None, opacity=0.35):
    source = Path(filename).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if view not in ROTATIONS:
        raise ValueError(f"Unknown reference view: {view}")
    if not math.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError("Opacity must be between zero and one")
    position = tuple(location if location is not None else bpy.context.scene.cursor.location)
    if len(position) != 3 or not all(math.isfinite(float(x)) for x in position):
        raise ValueError("Reference location must have three finite coordinates")
    scale = unit_scale()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    image = bpy.data.images.load(str(source), check_existing=False)
    try:
        if min(image.size) <= 0:
            raise ValueError(f"Image could not be decoded: {source}")
        image.pack()
    except Exception:
        bpy.data.images.remove(image)
        raise
    obj = bpy.data.objects.new(f"REF | {view} | {source.stem}", None)
    reference_collection().objects.link(obj)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    set_display_size(obj, 1.0 / scale)  # Display size only; not a measured dimension.
    obj.empty_image_depth = "BACK"
    obj.color[3] = opacity
    obj.location = position
    obj.rotation_euler = tuple(math.radians(x) for x in ROTATIONS[view])
    obj.hide_render = True
    obj[TAG] = True
    obj["source_file"] = str(source)
    obj["source_sha256"] = digest
    obj["reference_view"] = view
    obj["scale_basis"] = "uncalibrated_display_only"
    obj["geometry_status"] = "reference_image_only; no reconstructed geometry"
    return obj


def require_reference(obj):
    if obj is None or obj.type != "EMPTY" or not obj.get(TAG) or obj.data is None:
        raise ValueError("Select an imported local reference image")
    return obj


def pixel_point(obj, point):
    width, height = require_reference(obj).data.size
    if len(point) != 2 or not all(math.isfinite(float(x)) for x in point):
        raise ValueError("Pixel points must each have two finite coordinates")
    x, y = map(float, point)
    if not (0 <= x <= width and 0 <= y <= height):
        raise ValueError(f"Pixel coordinates must lie within {width} x {height}")
    return x, y


def pixel_to_world(obj, point):
    """Pixel origin is the image's top-left; Blender image offsets are respected."""
    x, y = pixel_point(obj, point)
    width, height = obj.data.size
    image_width = obj.empty_display_size * width / max(width, height)
    image_height = obj.empty_display_size * height / max(width, height)
    offset_x, offset_y = obj.empty_image_offset
    return obj.matrix_world @ Vector(((x / width + offset_x) * image_width,
                                     (1 - y / height + offset_y) * image_height, 0))


def calibrate(obj, point_a, point_b, known_distance_mm, basis="photo_planar_estimate"):
    require_reference(obj)
    point_a, point_b = pixel_point(obj, point_a), pixel_point(obj, point_b)
    known = float(known_distance_mm)
    if not math.isfinite(known) or known <= 0:
        raise ValueError("Known distance in mm must be finite and positive")
    if basis not in {"photo_planar_estimate", "orthographic_document"}:
        raise ValueError("Scale basis must identify a photo estimate or orthographic document")
    distance_pixels = math.dist(point_a, point_b)
    if distance_pixels < 1e-6:
        raise ValueError("Calibration endpoints must be different")
    bpy.context.view_layer.update()
    # Measure through the world matrix: parenting and existing uniform scale are retained.
    current_m = (pixel_to_world(obj, point_b) - pixel_to_world(obj, point_a)).length * unit_scale()
    if current_m < 1e-12:
        raise ValueError("Reference has a zero world-space scale")
    world_scale = obj.matrix_world.to_scale()
    if min(world_scale) <= 0 or max(world_scale) - min(world_scale) > 1e-5 * max(world_scale):
        raise ValueError("Nonuniform reference scale cannot establish one image scale")
    set_display_size(obj, obj.empty_display_size * (known / 1000) / current_m)
    obj["scale_basis"] = basis
    obj["calibration_json"] = json.dumps({
        "pixel_origin": "top_left", "point_a": point_a, "point_b": point_b,
        "known_distance_mm": known, "basis": basis,
        "limitation": "One in-plane scale; no perspective correction, depth or camera calibration",
    }, ensure_ascii=False)
    bpy.context.view_layer.update()
    return object_report(obj)


def object_report(obj):
    require_reference(obj)
    report = {"object": obj.name, "source_file": obj["source_file"],
              "source_sha256": obj["source_sha256"], "view": obj["reference_view"],
              "image_size_px": list(obj.data.size), "packed": bool(obj.data.packed_file),
              "scale_basis": obj["scale_basis"], "geometry_status": obj["geometry_status"]}
    if obj.get("calibration_json"):
        calibration = json.loads(obj["calibration_json"])
        current_mm = (pixel_to_world(obj, calibration["point_b"]) -
                      pixel_to_world(obj, calibration["point_a"])).length * unit_scale() * 1000
        uniform = obj.matrix_world.to_scale()
        calibration["current_distance_mm"] = current_mm
        calibration["current_scale_valid"] = (
            min(uniform) > 0 and max(uniform) - min(uniform) <= 1e-5 * max(uniform)
            and math.isclose(current_mm, calibration["known_distance_mm"], rel_tol=1e-5, abs_tol=1e-3))
        report["calibration"] = calibration
    return report


def write_manifest(filename):
    bpy.context.view_layer.update()
    report = {"schema_version": 1, "workflow": "local_photo_reference",
              "geometry_generated": False,
              "references": [object_report(obj) for obj in bpy.context.scene.objects if obj.get(TAG)]}
    Path(filename).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


class LocalPhotoSettings(bpy.types.PropertyGroup):
    view: bpy.props.EnumProperty(name="参考方向", items=VIEWS, default="FRONT")
    point_a: bpy.props.FloatVectorProperty(name="像素点 A", size=2, default=(0, 0), min=0)
    point_b: bpy.props.FloatVectorProperty(name="像素点 B", size=2, default=(100, 0), min=0)
    known_mm: bpy.props.FloatProperty(name="已知距离 (mm)", default=1000, min=0.001)
    basis: bpy.props.EnumProperty(name="尺寸来源", items=[
        ("photo_planar_estimate", "照片平面比例估计", "Does not correct perspective"),
        ("orthographic_document", "正交图 / 扫描图标定", "Use only for an orthographic document")])


class LOCALPHOTO_OT_import(bpy.types.Operator, ImportHelper):
    bl_idname = "local_photo.import_images"
    bl_label = "导入本地参考图"
    bl_options = {"REGISTER", "UNDO"}
    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp", options={"HIDDEN"})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "请先切换到物体模式")
            return {"CANCELLED"}
        settings = context.scene.local_photo_settings
        paths = [Path(self.directory) / item.name for item in self.files] or [Path(self.filepath)]
        imported, errors = [], []
        for path in paths:
            try:
                imported.append(load_reference(path, settings.view))
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        if imported:
            for selected in context.selected_objects:
                selected.select_set(False)
            for obj in imported:
                obj.select_set(True)
            context.view_layer.objects.active = imported[-1]
            settings.point_a = (0, 0)
            settings.point_b = (imported[-1].data.size[0], 0)
        if errors:
            self.report({"WARNING"}, "; ".join(errors))
        return {"FINISHED"} if imported else {"CANCELLED"}


class LOCALPHOTO_OT_calibrate(bpy.types.Operator):
    bl_idname = "local_photo.calibrate"
    bl_label = "按两点已知距离标定"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.local_photo_settings
        try:
            calibrate(context.active_object, settings.point_a, settings.point_b,
                      settings.known_mm, settings.basis)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "已记录平面比例与来源；透视和深度仍需核实")
        return {"FINISHED"}


class LOCALPHOTO_OT_export(bpy.types.Operator, ExportHelper):
    bl_idname = "local_photo.export_manifest"
    bl_label = "导出参考图与标定记录"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            write_manifest(self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class LOCALPHOTO_PT_panel(bpy.types.Panel):
    bl_label = "本地照片 / 图纸参考"
    bl_idname = "LOCALPHOTO_PT_reference"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "本地参考图"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.local_photo_settings
        layout.prop(settings, "view")
        layout.operator(LOCALPHOTO_OT_import.bl_idname, icon="IMAGE_DATA")
        layout.label(text="图片自动打包；实体需另行建模")
        obj = context.active_object
        if obj is not None and obj.get(TAG):
            box = layout.box()
            box.label(text=f"{obj.data.size[0]} x {obj.data.size[1]} px")
            box.prop(obj, "color", index=3, text="参考图透明度")
            box.label(text="像素坐标以图片左上角为原点")
            box.prop(settings, "point_a")
            box.prop(settings, "point_b")
            box.prop(settings, "known_mm")
            box.prop(settings, "basis")
            box.operator(LOCALPHOTO_OT_calibrate.bl_idname)
            box.label(text={"uncalibrated_display_only": "未标定：仅作显示参考",
                            "photo_planar_estimate": "已记录照片平面比例估计",
                            "orthographic_document": "已记录正交图比例"}.get(obj.get("scale_basis"), "未标定"))
            box.label(text="单张透视图不能确定深度")
        layout.operator(LOCALPHOTO_OT_export.bl_idname, icon="EXPORT")


CLASSES = (LocalPhotoSettings, LOCALPHOTO_OT_import, LOCALPHOTO_OT_calibrate,
           LOCALPHOTO_OT_export, LOCALPHOTO_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.local_photo_settings = bpy.props.PointerProperty(type=LocalPhotoSettings)


def unregister():
    del bpy.types.Scene.local_photo_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
