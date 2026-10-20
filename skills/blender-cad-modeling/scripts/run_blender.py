"""Launch local Blender without opening a terminal window or changing preferences."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def config_path():
    """Keep machine settings outside the installed skill so updates preserve them."""
    override = os.environ.get("BLENDER_CAD_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    codex_directory = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return codex_directory.expanduser() / "environments/blender-cad/config.json"


def config():
    references = Path(__file__).resolve().parents[1] / "references"
    result = json.loads((references / "local-environment.example.json").read_text(encoding="utf-8"))
    local = config_path()
    if os.environ.get("BLENDER_CAD_CONFIG") and not local.is_file():
        raise FileNotFoundError(f"BLENDER_CAD_CONFIG does not exist: {local}")
    # Accept an old installation's settings while migrating to user-level config.
    for source in (references / "local-environment.json", local):
        if source.is_file():
            settings = json.loads(source.read_text(encoding="utf-8-sig"))
            if not isinstance(settings, dict):
                raise ValueError(f"Expected a JSON object in {source}")
            result.update(settings)
    for key, variable in {
        "blender": "BLENDER_EXECUTABLE",
        "python": "BLENDER_CAD_PYTHON",
        "dwg_converter": "LIBREDWG_DWG2DXF",
        "dwg_writer": "LIBREDWG_DXF2DWG",
        "autocad_core": "AUTOCAD_CORE_CONSOLE",
    }.items():
        if os.environ.get(variable):
            result[key] = os.environ[variable]
        value = result.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"Configuration field {key} must be a string")
        if value:
            result[key] = str(Path(os.path.expandvars(value)).expanduser())
    if not result.get("blender"):
        binary = shutil.which("blender")
        if not binary and os.name == "nt":
            for variable in ("ProgramFiles", "ProgramFiles(x86)"):
                location = os.environ.get(variable)
                if location:
                    candidates = sorted((Path(location) / "Blender Foundation").glob("Blender */blender.exe"), reverse=True)
                    binary = next((str(path) for path in candidates if path.is_file()), None)
                    if binary:
                        break
        result["blender"] = binary or ""
    result["python"] = result.get("python") or sys.executable
    result["dwg_converter"] = result.get("dwg_converter") or shutil.which("dwg2dxf") or ""
    result["dwg_writer"] = result.get("dwg_writer") or shutil.which("dxf2dwg") or ""
    return result


def hidden_process():
    if os.name != "nt":
        return {}
    # Hide the startup window while retaining inherited console handles.
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startup}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path)
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--use-preferences", action="store_true")
    parser.add_argument("--threads", type=int, default=4, help="Render threads; 0 uses Blender automatic selection")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.threads < 0:
        parser.error("--threads must be zero or positive")
    binary = Path(config()["blender"])
    if not binary.is_file():
        parser.error(f"Blender executable not found: {binary}. Run scripts/configure.py --blender <executable> first.")
    if not args.script and not args.blend:
        parser.error("Provide --script or --blend")
    for path in (args.blend, args.script):
        if path and not path.is_file():
            parser.error(f"File not found: {path}")
    command = [str(binary)]
    if not args.ui:
        command.extend(["--background", "--threads", str(args.threads)])
    if not args.use_preferences:
        command.append("--factory-startup")
    command.append("--disable-autoexec")
    if args.blend:
        command.append(str(args.blend.resolve()))
    if args.script:
        command.extend(["--python-exit-code", "1", "--python", str(args.script.resolve())])
    if args.args:
        command.extend(args.args if args.args[0] == "--" else ["--", *args.args])
    if args.ui:
        process = subprocess.Popen(command)
        print(json.dumps({"pid": process.pid, "opened": str(args.blend or args.script)}, ensure_ascii=False))
    else:
        result = subprocess.run(command, **hidden_process())
        if result.returncode:
            print(f"Blender failed with process code {result.returncode}", file=sys.stderr)
        sys.exit(1 if result.returncode else 0)


if __name__ == "__main__":
    main()
