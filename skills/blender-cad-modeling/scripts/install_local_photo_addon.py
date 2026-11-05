"""Run inside Blender with user preferences: install/enable the bundled local-only add-on."""
import json
from pathlib import Path
import shutil
import sys

import addon_utils
import bpy


def main():
    source = Path(__file__).resolve().parents[1] / "assets/local_photo_reference/__init__.py"
    addons = Path(bpy.utils.user_resource("SCRIPTS", path="addons", create=True))
    destination = addons / "local_photo_reference"
    target = destination / "__init__.py"
    if target.is_file() and target.read_bytes() != source.read_bytes():
        # Keep an inspectable previous version; never recursively remove an add-on directory.
        backup = target.with_suffix(".py.previous")
        if backup.exists():
            raise FileExistsError(f"Review the existing add-on backup before replacing it: {backup}")
        shutil.copy2(target, backup)
    destination.mkdir(exist_ok=True)
    if "local_photo_reference" in sys.modules:
        addon_utils.disable("local_photo_reference", default_set=True)
        del sys.modules["local_photo_reference"]
    shutil.copy2(source, target)
    bpy.utils.refresh_script_paths()
    addon_utils.modules_refresh()
    module = addon_utils.enable("local_photo_reference", default_set=True, persistent=True)
    if module is None or not addon_utils.check("local_photo_reference")[1]:
        raise RuntimeError("Local Photo Reference could not be enabled")
    bpy.ops.wm.save_userpref()
    print(json.dumps({"addon": str(target), "enabled": True,
                      "network_required": False, "third_party_packages": []}, ensure_ascii=False))


if __name__ == "__main__":
    main()
