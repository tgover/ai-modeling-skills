"""Run an existing SolidWorks VBA macro project in an already-open application."""
import argparse
import json
from pathlib import Path
import sys

from sw_status import existing_session, value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--macro", type=Path, required=True)
    parser.add_argument("--module", required=True, help="Module name shown in the VBA editor")
    parser.add_argument("--procedure", default="main")
    args = parser.parse_args()
    macro = args.macro.expanduser().resolve()
    if macro.suffix.lower() != ".swp":
        parser.error("Provide a saved .swp macro project. A .bas source file cannot be executed directly.")
    if not macro.is_file():
        parser.error(f"Macro project does not exist: {macro}")
    result = {"macro": str(macro), "module": args.module, "procedure": args.procedure,
              "runtime_modeling_verified": False}
    try:
        import pythoncom
        from win32com.client import VARIANT
        with existing_session() as app:
            result["revision"] = str(value(app.RevisionNumber))
            error = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            invoked = bool(app.RunMacro2(str(macro), args.module, args.procedure, 0, error))
            result["run_macro_error"] = int(error.value)
        result["status"] = "macro_invoked" if invoked and result["run_macro_error"] == 0 else "macro_failed"
        result["next_step"] = "Read the macro's own validation report, reopen outputs, and check geometry before accepting the model."
    except Exception as exc:
        result.update(status="connection_or_macro_failed", message=str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "macro_invoked" else 1


if __name__ == "__main__":
    sys.exit(main())
