"""Configure this computer for the skill, or check installed tools and dependencies."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

from run_blender import config, config_path, hidden_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Full path to blender.exe")
    parser.add_argument("--dwg-converter", type=Path, help="Optional LibreDWG dwg2dxf.exe")
    parser.add_argument("--dwg-writer", type=Path, help="Optional LibreDWG dxf2dwg.exe (roundtrip tests)")
    parser.add_argument("--autocad-core", type=Path, help="Optional AutoCAD Core Console; requires separate validation")
    parser.add_argument("--check", action="store_true", help="Read-only validation; do not write settings")
    args = parser.parse_args()
    try:
        settings = config()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for key, supplied in {
        "blender": args.blender,
        "dwg_converter": args.dwg_converter,
        "dwg_writer": args.dwg_writer,
        "autocad_core": args.autocad_core,
    }.items():
        if supplied is not None:
            binary = supplied.expanduser().resolve()
            if not binary.is_file():
                parser.error(f"Executable does not exist: {binary}")
            settings[key] = str(binary)
    # The interpreter running this command is the host environment being configured.
    settings["python"] = sys.executable
    blender = Path(settings["blender"])
    if not blender.is_file():
        parser.error("Blender not found. Install Blender, then supply --blender <full executable path>.")
    try:
        completed = subprocess.run([str(blender), "--version"], capture_output=True,
                                   timeout=30, **hidden_process())
        version = completed.stdout.decode("utf-8", errors="replace").splitlines()
        if completed.returncode or not version or not version[0].startswith("Blender "):
            parser.error("Selected executable did not return a Blender version.")
    except (OSError, subprocess.TimeoutExpired) as exc:
        parser.error(f"Could not run Blender: {exc}")
    settings["blender_version"] = version[0]
    required = Path(__file__).resolve().parents[1] / "references/requirements-lock.txt"
    packages, problems = {}, []
    for line in required.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        packages[name] = installed
        if installed != expected:
            problems.append(f"{name}: expected {expected}, found {installed or 'not installed'}")
    destination = config_path()
    if not args.check:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = {
        "status": "dependencies_required" if problems else "ready_for_selftest",
        "configuration": str(destination), "configuration_written": not args.check,
        "blender_version": settings["blender_version"], "python": settings["python"],
        "packages": packages, "dependency_problems": problems,
        "dwg_converter_available": bool(settings["dwg_converter"] and Path(settings["dwg_converter"]).is_file()),
        "next_step": "Install references/requirements-lock.txt, then run scripts/selftest.py in this Python environment.",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
