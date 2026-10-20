"""Read SolidWorks registration and an existing session; never launch or edit it."""
from contextlib import contextmanager
import json
import os
import sys


def value(member):
    """Late-bound COM can expose zero-argument methods as values."""
    return member() if callable(member) else member


@contextmanager
def existing_session():
    if sys.platform != "win32":
        raise RuntimeError("Desktop SolidWorks COM requires Windows.")
    try:
        import pythoncom
        import win32com.client.dynamic
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("Install references/requirements.txt in this Python environment.") from exc
    pythoncom.CoInitialize()
    app = active = None
    try:
        active = win32com.client.GetActiveObject(os.environ.get("SOLIDWORKS_PROGID", "SldWorks.Application"))
        app = win32com.client.dynamic.Dispatch(active)
        yield app
    finally:
        app = active = None
        pythoncom.CoUninitialize()


def get_status():
    result = {"status": "unavailable", "runtime_modeling_verified": False,
              "progid": os.environ.get("SOLIDWORKS_PROGID", "SldWorks.Application"),
              "python_version": sys.version.split()[0]}
    if sys.platform != "win32":
        return {**result, "status": "unsupported_platform", "message": "Windows is required for COM access."}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, result["progid"] + "\\CLSID") as key:
            result["registered_clsid"] = winreg.QueryValueEx(key, None)[0]
    except FileNotFoundError:
        return {**result, "status": "not_registered", "message": "SolidWorks COM is not registered for this ProgID. Install or repair desktop SolidWorks on this computer."}
    except OSError as exc:
        return {**result, "status": "registration_unreadable", "message": str(exc)}
    try:
        with existing_session() as app:
            result["revision"] = str(value(app.RevisionNumber))
            document = app.ActiveDoc
            result["active_document"] = str(value(document.GetTitle)) if document is not None else None
            result["document_type"] = int(value(document.GetType)) if document is not None else None
            document = None
        result["status"] = "connected_read_only"
        result["message"] = "An existing session was read; no modeling operation was tested."
    except Exception as exc:
        result.update(status="connection_failed", message=str(exc),
                      next_step="Open SolidWorks manually, dismiss modal dialogs, and use the same Windows user and elevation.")
    return result


if __name__ == "__main__":
    status = get_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    sys.exit(0 if status["status"] == "connected_read_only" else 2)
