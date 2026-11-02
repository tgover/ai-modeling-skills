"""Run inside a freshly reopened Blender file. Never save or alter the input file."""
import argparse
from collections import Counter
import fnmatch
import itertools
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

GEOMETRY = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def vector(value):
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
        raise ValueError("Expected a finite three-coordinate vector")
    return Vector(value)


def number(value, minimum=0):
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError("Expected a finite nonnegative number")
    return value


def inspect(spec):
    checks, failures, cache = [], [], {}
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    physical = {o.name: o for o in scene.objects if o.type in GEOMETRY}

    def check(label, function):
        try:
            detail = function()
            checks.append({"name": label, "status": "passed", "detail": detail})
        except Exception as exc:
            message = f"{label}: {exc}"
            checks.append({"name": label, "status": "failed", "detail": str(exc)})
            failures.append(message)

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def names(patterns):
        require(isinstance(patterns, list) and bool(patterns), "Expected nonempty object selector list")
        result = set()
        for pattern in patterns:
            require(isinstance(pattern, str) and bool(pattern), "Object selector must be a string")
            matched = {name for name in physical if fnmatch.fnmatchcase(name, pattern)}
            require(bool(matched), f"No physical object matches {pattern}")
            result.update(matched)
        return sorted(result)

    def mesh(name):
        if name not in cache:
            obj = physical[name]
            evaluated = obj.evaluated_get(depsgraph)
            data = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
            data.transform(evaluated.matrix_world)
            data.calc_loop_triangles()
            points = [v.co.copy() for v in data.vertices]
            triangles = [tuple(t.vertices) for t in data.loop_triangles]
            require(bool(points) and bool(triangles), f"Empty geometry: {name}")
            require(all(math.isfinite(x) for p in points for x in p), f"Nonfinite geometry: {name}")
            bounds = ([min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)])
            edges = Counter(tuple(sorted(edge)) for t in triangles for edge in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
            cache[name] = {"mesh": data, "points": points, "triangles": triangles, "bounds": bounds,
                           "closed": all(count == 2 for count in edges.values()),
                           "bvh": BVHTree.FromPolygons(points, triangles, all_triangles=True)}
        return cache[name]

    def bounds(selected):
        points = [p for name in selected for p in mesh(name)["points"]]
        return Vector([min(p[i] for p in points) for i in range(3)]), Vector([max(p[i] for p in points) for i in range(3)])

    selected = []

    def coverage():
        selected.extend(names(spec["objects"]))
        excluded = set()
        for item in spec.get("excluded_objects", []):
            require(bool(item.get("reason", "").strip()), "Excluded geometry needs a reason")
            excluded.update(names([item["object"]]))
        require(not excluded.intersection(selected), "Selected and excluded objects overlap")
        missing = set(physical) - set(selected) - excluded
        require(not missing, f"Unclassified physical objects: {sorted(missing)[:20]}")
        for name in selected:
            mesh(name)
        return {"physical_count": len(physical), "inspected_count": len(selected), "excluded": sorted(excluded)}

    check("inventory_and_finite_geometry", coverage)
    check("meter_scene_units", lambda: require(scene.unit_settings.system == "METRIC" and abs(scene.unit_settings.scale_length - 1) < 1e-9, "Use metric scene units with scale_length=1"))

    for index, item in enumerate(spec.get("counts", [])):
        def count_objects(item=item):
            actual = len(names(item["objects"]))
            require(actual == int(item["expected"]), f"Object count {actual}; expected {item['expected']}")
            return {"actual": actual}
        check(f"count/{index}", count_objects)

    for index, item in enumerate(spec.get("dimensions", [])):
        def measure(item=item):
            low, high = bounds(names(item["objects"]))
            actual = (high - low) * 1000
            expected = vector(item["expected_mm"])
            tolerance = number(item.get("tolerance_mm", 0.5))
            require(all(x > 0 for x in expected), "Expected dimensions must be positive")
            require(all(abs(actual[i] - expected[i]) <= tolerance for i in range(3)), f"Actual {list(actual)} mm; expected {list(expected)} ± {tolerance} mm")
            return {"actual_mm": list(actual), "expected_mm": list(expected), "tolerance_mm": tolerance}
        check(f"dimensions/{index}", measure)

    def port(item):
        obj = scene.objects.get(item["object"])
        require(obj is not None and obj.type in GEOMETRY, f"Missing physical port owner {item['object']}")
        point = obj.matrix_world @ vector(item["point_m"])
        axis = obj.matrix_world.to_3x3() @ vector(item["axis"])
        require(axis.length > 1e-12, "Port axis is zero")
        return point, axis.normalized()

    for index, item in enumerate(spec.get("connections", [])):
        def connect(item=item):
            p, u = port(item["a"])
            q, v = port(item["b"])
            gap = (p - q).length * 1000
            require(gap <= number(item.get("max_gap_mm", 0.5)), f"Port gap {gap:.6f} mm")
            target = -v if item.get("opposed_axes", True) else v
            angle = math.degrees(u.angle(target))
            require(angle <= number(item.get("angle_tolerance_deg", 1)), f"Port axis mismatch {angle:.6f} degrees")
            return {"gap_mm": gap, "axis_error_deg": angle}
        check(f"connection/{index}", connect)

    for index, item in enumerate(spec.get("contacts", [])):
        def contact(item=item):
            a, b = mesh(item["a"]), mesh(item["b"])
            distances = [b["bvh"].find_nearest(p)[3] for p in a["points"]]
            distances.extend(a["bvh"].find_nearest(p)[3] for p in b["points"])
            gap = 0 if a["bvh"].overlap(b["bvh"]) else min(distances) * 1000
            require(gap <= number(item.get("max_gap_mm", 0.5)), f"Detached installation pair; sampled surface gap {gap:.6f} mm")
            return {"sampled_surface_gap_mm": gap, "method": "bidirectional vertex-to-triangle plus triangle intersections"}
        check(f"contact/{index}", contact)

    for index, item in enumerate(spec.get("connected_parts", [])):
        def continuity(item=item):
            data = mesh(item["object"])["mesh"]
            parent = list(range(len(data.vertices)))
            def find(v):
                while parent[v] != v:
                    parent[v] = parent[parent[v]]
                    v = parent[v]
                return v
            for edge in data.edges:
                a, b = edge.vertices
                parent[find(a)] = find(b)
            count = len({find(i) for i in range(len(parent))})
            require(count == int(item.get("expected", 1)), f"Expected {item.get('expected', 1)} connected mesh islands; found {count}")
            return {"mesh_islands": count}
        check(f"connected_parts/{index}", continuity)

    def intersection_volume(a, b):
        require(a["closed"] and b["closed"], "Volume intersection requires closed solids; open geometry needs separate review")
        temporary = []
        try:
            for source in (a, b):
                obj = bpy.data.objects.new("_model_qa_boolean", source["mesh"])
                scene.collection.objects.link(obj)
                temporary.append(obj)
            mod = temporary[0].modifiers.new("_qa_intersection", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", temporary[1]
            bpy.context.view_layer.update()
            evaluated = temporary[0].evaluated_get(bpy.context.evaluated_depsgraph_get())
            data = evaluated.to_mesh()
            bm = bmesh.new()
            try:
                bm.from_mesh(data)
                return abs(bm.calc_volume(signed=True)) * 1e9 if bm.faces else 0.0
            finally:
                bm.free()
                evaluated.to_mesh_clear()
        finally:
            for obj in temporary:
                bpy.data.objects.remove(obj, do_unlink=True)

    def collisions():
        group = names(spec["collision_objects"])
        allowed = set()
        for item in spec.get("allowed_intersections", []):
            require(bool(item.get("reason", "").strip()), "Each permitted intersection needs a reason")
            require(item["a"] in group and item["b"] in group and item["a"] != item["b"], "Permitted intersections must name one exact pair in the collision set")
            allowed.add(tuple(sorted((item["a"], item["b"]))))
        candidates, problems = 0, []
        for aname, bname in itertools.combinations(group, 2):
            if tuple(sorted((aname, bname))) in allowed:
                continue
            a, b = mesh(aname), mesh(bname)
            if any(min(a["bounds"][1][i], b["bounds"][1][i]) - max(a["bounds"][0][i], b["bounds"][0][i]) <= 1e-9 for i in range(3)):
                continue
            candidates += 1
            volume = intersection_volume(a, b)
            if volume > 0.01:
                problems.append({"a": aname, "b": bname, "intersection_mm3": volume})
        require(not problems, json.dumps(problems[:20]))
        return {"objects": len(group), "exact_boolean_candidates": candidates, "explicit_exemptions": len(allowed)}
    if spec.get("collision_objects"):
        check("solid_intersections", collisions)

    for index, item in enumerate(spec.get("bore_paths", [])):
        def bore(item=item):
            group = names(item["objects"])
            points = [vector(p) for p in item["points_m"]]
            require(len(points) >= 2, "Bore path requires at least two world-space points")
            radius = number(item.get("sample_radius_m", 0))
            for start, end in zip(points, points[1:]):
                delta = end - start
                require(delta.length > 1e-6, "Zero-length bore segment")
                direction = delta.normalized()
                normal = direction.cross(Vector((1, 0, 0)) if abs(direction.x) < 0.9 else Vector((0, 1, 0))).normalized()
                tangent = direction.cross(normal)
                offsets = [Vector((0, 0, 0))]
                if radius:
                    offsets.extend([normal * radius, -normal * radius, tangent * radius, -tangent * radius])
                for offset in offsets:
                    for name in group:
                        hit, _, _, distance = mesh(name)["bvh"].ray_cast(start + offset + direction * 1e-7, direction, delta.length - 2e-7)
                        require(hit is None, f"Flow-path sample blocked by {name} at {list(hit) if hit is not None else None}")
            return {"segments": len(points) - 1, "rays_per_segment": 5 if radius else 1, "scope": "sampled paths, not full hydraulic or inner-volume certification"}
        check(f"bore_path/{index}", bore)

    def overview():
        settings = spec.get("overview", {})
        window = bpy.context.window
        require(window is not None, "No saved window state")
        if settings.get("scene"):
            require(window.scene.name == settings["scene"], f"Default scene is {window.scene.name}")
        targets = names(settings.get("objects", spec["objects"]))
        low, high = bounds(targets)
        center, radius = (low + high) / 2, max((high - low).length / 2, 1e-6)
        require(all(physical[n].visible_get(view_layer=window.view_layer) for n in targets), "Overview targets are hidden in the saved view layer")
        spaces = [(area, area.spaces.active) for area in window.screen.areas if area.type == "VIEW_3D"]
        require(bool(spaces), "Saved workspace has no 3D overview")
        errors = []
        for area, space in spaces:
            region = space.region_3d
            if region.view_perspective == "CAMERA" or space.local_view or space.lock_object:
                errors.append("Camera/local/locked view")
                continue
            distance = region.view_distance
            offset = (region.view_location - center).length
            aspect = min(1.0, max(area.height, 1) / max(area.width, 1))
            half_angle = math.atan(16.0 / max(space.lens, 1) * aspect)
            minimum_distance = max(radius * 2.5, radius / math.sin(half_angle)) + offset
            if distance < minimum_distance:
                errors.append("Overview zoom/center is too tight for the model bounds")
                continue
            if space.clip_end < distance + radius + offset or space.clip_start > max(distance - radius - offset, 0):
                errors.append("Overview clipping excludes model bounds")
                continue
            return {"view_distance_m": distance, "minimum_distance_m": minimum_distance, "bounds_radius_m": radius,
                    "lens_mm": space.lens, "method": "conservative lens/aspect/sphere/center/clip checks; final image review still required"}
        raise ValueError("; ".join(errors))
    check("saved_whole_model_overview", overview)

    def resources():
        missing = []
        for image in bpy.data.images:
            if image.source == "FILE" and not image.packed_file and image.filepath:
                if not Path(bpy.path.abspath(image.filepath, library=image.library)).is_file():
                    missing.append("image:" + image.name)
        for font in bpy.data.fonts:
            if font.filepath and font.filepath != "<builtin>" and not font.packed_file:
                if not Path(bpy.path.abspath(font.filepath, library=font.library)).is_file():
                    missing.append("font:" + font.name)
        for library in bpy.data.libraries:
            if not Path(bpy.path.abspath(library.filepath)).is_file():
                missing.append("library:" + library.name)
        require(not missing, f"Missing dependencies: {missing}")
        return {"checked": "file images, fonts and linked libraries; other external simulations/media need task-specific checks"}
    check("external_dependencies", resources)
    inventory = [{"name": n, "type": physical[n].type, "selected": n in selected} for n in sorted(physical)]
    return {"checks": checks, "failures": failures, "inventory": inventory}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    try:
        spec = json.loads(args.contract.read_text(encoding="utf-8-sig"))
        result = inspect(spec)
    except Exception as exc:
        result = {"checks": [], "failures": [str(exc)], "inventory": []}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
