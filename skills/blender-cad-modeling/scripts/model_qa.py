"""Version-bound Blender acceptance and project-scoped Codex lifecycle hooks.

The hook reads reports; expensive Blender work runs in the normal tool workflow.
This is a quality guardrail for registered deliverables, not a security boundary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

VERSION = 1
SCRIPTS = Path(__file__).resolve().parent
CONTRACT_KEYS = {"schema_version", "model", "objects", "dimensions", "connections",
                 "contacts", "collision_objects", "allowed_intersections", "bore_paths",
                 "required_views", "review_topics", "overview", "assumptions",
                 "excluded_objects", "connected_parts", "model_kind", "counts"}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_contract(path):
    path = Path(path).resolve()
    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema_version") != VERSION:
        raise ValueError("Contract must be a version 1 JSON object")
    if set(data) - CONTRACT_KEYS:
        raise ValueError(f"Unknown contract keys: {sorted(set(data) - CONTRACT_KEYS)}")
    if not isinstance(data.get("model"), str) or not data["model"]:
        raise ValueError("Contract requires model path")
    if not isinstance(data.get("objects"), list) or not data["objects"]:
        raise ValueError("List the physical objects to inspect")
    if any(not isinstance(x, str) or not x for x in data["objects"]):
        raise ValueError("objects must contain nonempty object names")
    if len(set(data["objects"])) != len(data["objects"]):
        raise ValueError("Duplicate object names")
    for key in ("dimensions", "connections", "contacts", "collision_objects",
                "allowed_intersections", "bore_paths", "required_views", "review_topics", "assumptions",
                "excluded_objects", "connected_parts", "counts"):
        if key in data and not isinstance(data[key], list):
            raise ValueError(f"{key} must be an array")
    views = data.get("required_views", ["overview", "detail"])
    if not views or any(not isinstance(x, str) or not x for x in views):
        raise ValueError("At least one named visual review view is required")
    if data.get("model_kind") not in ("general", "equipment", "piping"):
        raise ValueError("Declare model_kind: general, equipment or piping")
    if not data.get("dimensions") or not data.get("collision_objects"):
        raise ValueError("Declare dimensional checks and a collision object set")
    if data["model_kind"] == "piping" and any(not data.get(k) for k in ("connections", "contacts", "bore_paths")):
        raise ValueError("Piping models require connections, contacts and sampled bore paths")
    model = (path.parent / data["model"]).resolve()
    if model.suffix.lower() != ".blend":
        raise ValueError("Only Blender deliverables are supported by this gate")
    return data, model


def report_path(contract):
    return Path(str(Path(contract).resolve()) + ".report.json")


def review_path(contract):
    return Path(str(Path(contract).resolve()) + ".review.json")


def expected_check_names(data):
    names = {"inventory_and_finite_geometry", "meter_scene_units", "saved_whole_model_overview", "external_dependencies", "solid_intersections"}
    for field, prefix in (("dimensions", "dimensions"), ("counts", "count"), ("connections", "connection"),
                          ("contacts", "contact"), ("connected_parts", "connected_parts"), ("bore_paths", "bore_path")):
        names.update(f"{prefix}/{index}" for index in range(len(data.get(field, []))))
    return names


def review_failures(contract, data, model):
    failures = []
    try:
        review = read_json(review_path(contract))
        if review.get("model_sha256") != digest(model) or review.get("contract_sha256") != digest(contract):
            failures.append("Visual review belongs to an older model or contract")
        if not review.get("note", "").strip() or review.get("findings"):
            failures.append("Visual review is missing its note or has unresolved findings")
        for role in data.get("required_views", ["overview", "detail"]):
            evidence = review.get("views", {}).get(role)
            if not evidence or digest(evidence["path"]) != evidence["sha256"]:
                failures.append(f"Missing or changed review view: {role}")
        if review.get("review_topics") != data.get("review_topics", []):
            failures.append("Visual review did not record the contract's review topics")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failures.append(f"Visual review is unavailable: {exc}")
    return failures


def acceptance_failures(contract):
    """Recheck content hashes on every Stop; mtime alone is insufficient."""
    try:
        data, model = load_contract(contract)
        report = read_json(report_path(contract))
        failures = []
        if report.get("schema_version") != VERSION or report.get("status") != "passed":
            failures.extend(report.get("failures") or ["Acceptance report has not passed"])
        for key, path in (("model_sha256", model), ("contract_sha256", contract),
                          ("inspector_sha256", SCRIPTS / "inspect_model.py")):
            if report.get(key) != digest(path):
                failures.append(f"Acceptance report is stale: {key}")
        checks = report.get("checks")
        if (not checks or any(item.get("status") != "passed" for item in checks)
                or {item.get("name") for item in checks} != expected_check_names(data)
                or len(checks) != len(expected_check_names(data))):
            failures.append("Acceptance checks are incomplete or failed")
        failures.extend(review_failures(contract, data, model))
        if report.get("review_sha256") != digest(review_path(contract)):
            failures.append("Visual review changed after validation")
        return failures
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"Acceptance is unavailable: {exc}"]


def state_path(root, session):
    if not isinstance(session, str) or not session:
        raise ValueError("An exact Codex session_id is required")
    key = hashlib.sha256(session.encode("utf-8")).hexdigest()
    return Path(root).resolve() / ".model-qa" / "sessions" / key / "state.json"


def register(root, session, task, contract, resume=False):
    root, contract = Path(root).resolve(), Path(contract).resolve()
    _, model = load_contract(contract)
    if not contract.is_relative_to(root) or not model.is_relative_to(root):
        raise ValueError("The contract and model must stay within the selected project")
    path = state_path(root, session)
    state = read_json(path) if path.exists() else {}
    if state.get("task_id") != task:
        state = {"task_id": task, "contracts": [], "repair_requests": 0, "history": []}
    if str(contract) not in state["contracts"]:
        state["contracts"].append(str(contract))
    if state.get("suspended") and not resume:
        raise ValueError("Task was interrupted; use --resume only after the user resumes it")
    state["suspended"] = False
    write_json(path, state)
    return {"status": "registered", "task_id": task, "contracts": state["contracts"]}


def hook(root, payload):
    root = Path(root).resolve()
    if not Path(payload.get("cwd", root)).resolve().is_relative_to(root):
        return {}
    event, session = payload.get("hook_event_name"), payload.get("session_id")
    path = state_path(root, session)
    if event in ("SessionStart", "UserPromptSubmit"):
        context = (f"Blender quality gate is configured for this project. Current session_id={session!r}. "
                   f"For model creation/refinement read {SCRIPTS.parent / 'references/quality-gate.md'}. "
                   "Before editing register each delivery contract with this session_id and a task-id; "
                   "after saving run validate, inspect the required views, record-review, then validate again. "
                   "Do not register read-only questions, skill maintenance or test fixtures as deliverables. "
                   "Registration does not reset the repair budget for the same task-id. "
                   "A missing/stale report cannot be called passed; checks cover declared objects and relationships only.")
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
    if not path.exists():
        return {}
    state = read_json(path)
    if event == "Interrupt":
        state["suspended"] = True
        write_json(path, state)
        return {}
    if event != "Stop" or state.get("suspended"):
        return {}
    failures = []
    for contract in state.get("contracts", []):
        failures.extend(f"{Path(contract).name}: {x}" for x in acceptance_failures(contract))
    if not failures:
        state["last_status"] = "passed"
        write_json(path, state)
        return {}
    signature = hashlib.sha256(json.dumps(failures, ensure_ascii=False).encode()).hexdigest()
    state["history"].append({"at": time.time(), "signature": signature, "failures": failures[:12]})
    state["last_status"] = "failed"
    requests = state.get("repair_requests", 0)
    stalled = len(state["history"]) >= 2 and state["history"][-2]["signature"] == signature
    if state.get("report_only_sent"):
        write_json(path, state)
        return {"systemMessage": "建模验收未通过；自动修复已停止，不能报告为验收完成。"}
    summary = "\n".join(failures[:12])
    if requests >= 3 or (stalled and requests >= 2):
        state["report_only_sent"] = True
        result = {"decision": "block", "reason": "建模验收仍未通过，已达到修复上限或连续无进展。停止自动修复，向用户明确报告未通过项、已尝试措施及需要的资料；不得称为完成或通过。\n" + summary}
    else:
        state["repair_requests"] = requests + 1
        result = {"decision": "block", "reason": f"建模交付检查未通过（修复请求 {requests + 1}/3）。检查当前模型和验收单，修复后重跑 validate 并更新真实看图记录；不要改低标准、重新注册任务或绕过检查。\n" + summary}
    write_json(path, state)
    return result


def validate(contract, timeout=300):
    from run_blender import config, hidden_process
    contract = Path(contract).resolve()
    data, model = load_contract(contract)
    model_hash, contract_hash = digest(model), digest(contract)
    binary = Path(config()["blender"])
    if not binary.is_file():
        raise FileNotFoundError("Configured Blender executable is unavailable")
    with tempfile.TemporaryDirectory(prefix="model-qa-") as directory:
        output = Path(directory) / "inspection.json"
        log = Path(str(contract) + ".blender.log")
        command = [str(binary), "--background", "--factory-startup", "--disable-autoexec", str(model),
                   "--python-exit-code", "1", "--python", str(SCRIPTS / "inspect_model.py"),
                   "--", "--contract", str(contract), "--output", str(output)]
        with log.open("w", encoding="utf-8") as stream:
            try:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=timeout, **hidden_process())
                inspection = read_json(output) if output.exists() else {"checks": [], "failures": ["Blender inspection produced no report"]}
                if result.returncode:
                    inspection.setdefault("failures", []).append(f"Blender exited with code {result.returncode}")
            except subprocess.TimeoutExpired:
                inspection = {"checks": [], "failures": ["Blender inspection timed out"]}
    failures = list(inspection.get("failures", []))
    checks = inspection.get("checks", [])
    if (any(item.get("status") != "passed" for item in checks)
            or {item.get("name") for item in checks} != expected_check_names(data)
            or len(checks) != len(expected_check_names(data))):
        failures.append("Inspection did not pass every required check")
    failures.extend(review_failures(contract, data, model))
    if digest(model) != model_hash or digest(contract) != contract_hash:
        failures.append("Model or contract changed during inspection")
    if not inspection.get("checks"):
        failures.append("No geometry checks were executed")
    report = {"schema_version": VERSION, "status": "failed" if failures else "passed", "created_at": time.time(),
              "model_sha256": model_hash, "contract_sha256": contract_hash,
              "inspector_sha256": digest(SCRIPTS / "inspect_model.py"),
              "review_sha256": digest(review_path(contract)) if review_path(contract).exists() else None,
              "checks": inspection.get("checks", []), "failures": failures,
              "inventory": inspection.get("inventory", []), "scope": "Declared objects and relationships; visual review recorded separately; no engineering performance certification"}
    write_json(report_path(contract), report)
    return report


def record_review(contract, views, note, findings):
    from PIL import Image
    contract = Path(contract).resolve()
    data, model = load_contract(contract)
    records = {}
    for entry in views:
        role, filename = entry.split("=", 1)
        if not role or role in records:
            raise ValueError("Use one image for each unique view role")
        path = Path(filename).resolve()
        with Image.open(path) as image:
            image.verify()
        records[role] = {"path": str(path), "sha256": digest(path)}
    if not note.strip() or set(data.get("required_views", ["overview", "detail"])) - set(records):
        raise ValueError("Record a meaningful review note and every required view")
    review = {"model_sha256": digest(model), "contract_sha256": digest(contract), "views": records,
              "note": note, "findings": findings, "review_topics": data.get("review_topics", []), "at": time.time()}
    write_json(review_path(contract), review)
    return {"status": "review_recorded", "unresolved_findings": findings}


def install_hooks(project):
    project = Path(project).resolve()
    path = project / ".codex" / "hooks.json"
    config = read_json(path) if path.exists() else {"description": "Project-scoped Blender delivery quality checks"}
    events = config.setdefault("hooks", {})
    for event in ("SessionStart", "UserPromptSubmit", "Stop", "Interrupt"):
        groups = events.setdefault(event, [])
        preserved = []
        for group in groups:
            handlers = [h for h in group.get("hooks", []) if not h.get("statusMessage", "").startswith("Model QA:")]
            if handlers:
                preserved.append({**group, "hooks": handlers})
        groups[:] = preserved
        args = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "hook", "--root", str(project)]
        command = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
        groups.append({"hooks": [{"type": "command", "command": command, "timeout": 3 if event == "Interrupt" else 30,
                                   "statusMessage": f"Model QA: {event}"}]})
    if path.exists():
        backup = path.with_name(f"hooks.before-model-qa.{time.time_ns()}.json")
        backup.write_bytes(path.read_bytes())
    write_json(path, config)
    return {"status": "configured_pending_user_trust", "path": str(path), "events": list(events),
            "next": "Review and trust the exact hook definitions using Codex /hooks; this installer never changes the trust store"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("register")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    p = sub.add_parser("validate")
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=300)
    p = sub.add_parser("record-review")
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--view", action="append", required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--finding", action="append", default=[])
    p = sub.add_parser("hook")
    p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("install-hooks")
    p.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "register":
            result = register(args.root, args.session, args.task_id, args.contract, args.resume)
        elif args.command == "validate":
            result = validate(args.contract, args.timeout)
        elif args.command == "record-review":
            result = record_review(args.contract, args.view, args.note, args.finding)
        elif args.command == "install-hooks":
            result = install_hooks(args.project)
        else:
            result = hook(args.root, json.load(sys.stdin))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if args.command == "hook":
            # A broken checker must not silently look like successful acceptance.
            result = {"systemMessage": f"Model QA hook failed: {exc}. No acceptance is established."}
        else:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
            return 2
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
