"""Generate VBA source for a four-hole plate; does not run or require SolidWorks."""
import argparse
import json
import math
from pathlib import Path


def vba_string(text):
    """Emit ASCII-only VBA source while retaining Unicode paths and literal quotes."""
    pieces, ascii_chars = [], []
    def flush():
        if ascii_chars:
            pieces.append('"' + ''.join(ascii_chars).replace('"', '""') + '"')
            ascii_chars.clear()
    for char in str(text):
        if ord(char) < 32:
            raise ValueError("Control characters are not supported in file paths.")
        if ord(char) < 127:
            ascii_chars.append(char)
        else:
            flush()
            encoded = char.encode("utf-16-le")
            for offset in range(0, len(encoded), 2):
                code = int.from_bytes(encoded[offset:offset + 2], "little")
                pieces.append(f"ChrW$(&H{code:04X})")
    flush()
    return " & ".join(pieces) if pieces else '""'


def check_dimensions(length, width, thickness, hole_diameter, edge_offset):
    values = (length, width, thickness, hole_diameter, edge_offset)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError("Dimensions must be finite positive millimeter values.")
    radius = hole_diameter / 2
    if edge_offset <= radius or 2 * edge_offset >= min(length, width):
        raise ValueError("Each hole must lie strictly inside the plate, at four distinct corner locations.")
    if length - 2 * edge_offset <= hole_diameter or width - 2 * edge_offset <= hole_diameter:
        raise ValueError("Neighboring holes must not overlap or touch.")


def generate(output, part_template, length=200, width=120, thickness=20,
             hole_diameter=24, edge_offset=30):
    check_dimensions(length, width, thickness, hole_diameter, edge_offset)
    template_path = str(part_template)
    if Path(template_path).suffix.lower() != ".prtdot":
        raise ValueError("Supply the target computer's .prtdot part template path.")
    output = Path(output).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose a new empty directory; existing files will not be replaced.")
    text = (Path(__file__).resolve().parents[1] / "assets/plate_with_holes.bas.template").read_text(encoding="ascii")
    replacements = {
        "OUTPUT_FOLDER": vba_string(output), "PART_TEMPLATE": vba_string(template_path),
        "LENGTH_MM": format(length, ".15g"), "WIDTH_MM": format(width, ".15g"),
        "THICKNESS_MM": format(thickness, ".15g"), "HOLE_DIAMETER_MM": format(hole_diameter, ".15g"),
        "EDGE_OFFSET_MM": format(edge_offset, ".15g"),
    }
    for key, replacement in replacements.items():
        text = text.replace("@@" + key + "@@", replacement)
    if "@@" in text:
        raise ValueError("Unresolved macro template marker.")
    if max(map(len, text.splitlines())) > 900:
        raise ValueError("Output/template path is too long for this VBA source generator.")
    output.mkdir(parents=True, exist_ok=True)
    source = output / "plate.bas"
    source.write_text(text, encoding="ascii")
    expected_volume = (length * width - 4 * math.pi * (hole_diameter / 2) ** 2) * thickness
    manifest = {
        "status": "source_generated", "runtime_modeling_verified": False,
        "target_api_baseline": "SOLIDWORKS 2022", "synthetic_example": True,
        "parameters_mm": dict(zip(("length", "width", "thickness", "hole_diameter", "edge_offset"),
                                  (length, width, thickness, hole_diameter, edge_offset))),
        "expected_hole_centers_mm": [[x, y] for y in (edge_offset, width - edge_offset)
                                    for x in (edge_offset, length - edge_offset)],
        "expected_volume_mm3": expected_volume, "expected_solid_bodies": 1,
        "macro_source": str(source), "part_template_on_target": template_path,
        "expected_outputs": ["plate.SLDPRT", "plate.step", "validation.txt"],
        "limitations": ["VBA compilation and real SW execution are not verified by source generation.",
                        "Demo sketch geometry is not fully dimension-constrained.",
                        "After running, reopen files and inspect hole locations and native features."],
    }
    (output / "parameters.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--part-template", required=True, help="Actual target computer part template; verified at macro runtime")
    for name, default in (("length", 200), ("width", 120), ("thickness", 20),
                          ("hole-diameter", 24), ("edge-offset", 30)):
        parser.add_argument("--" + name + "-mm", type=float, default=default)
    args = parser.parse_args()
    try:
        result = generate(args.output, args.part_template, args.length_mm, args.width_mm,
                          args.thickness_mm, args.hole_diameter_mm, args.edge_offset_mm)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({k: result[k] for k in ("status", "runtime_modeling_verified", "macro_source")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
