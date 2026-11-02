"""Behavioral tests for version binding, bounded retries and hook configuration."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/blender-cad-modeling/scripts/model_qa.py"
spec = importlib.util.spec_from_file_location("model_qa", SCRIPT)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.model = self.root / "model.blend"
        self.model.write_bytes(b"synthetic-content-for-gate-tests")
        self.contract = self.root / "acceptance.json"
        self.data = {"schema_version": 1, "model_kind": "general", "model": "model.blend", "objects": ["body"],
                     "dimensions": [{"objects": ["body"], "expected_mm": [100, 100, 100]}],
                     "collision_objects": ["body"], "required_views": ["overview"], "review_topics": ["reference proportions"]}
        qa.write_json(self.contract, self.data)
        self.payload = {"session_id": "chat-A", "cwd": str(self.root), "hook_event_name": "Stop", "turn_id": "one"}

    def tearDown(self):
        self.tmp.cleanup()

    def passed_report(self):
        image = self.root / "overview.png"
        image.write_bytes(b"image-fixture-used-only-for-content-hash-tests")
        qa.write_json(qa.review_path(self.contract), {"model_sha256": qa.digest(self.model), "contract_sha256": qa.digest(self.contract),
                      "note": "Reviewed", "findings": [], "review_topics": self.data["review_topics"],
                      "views": {"overview": {"path": str(image), "sha256": qa.digest(image)}}})
        qa.write_json(qa.report_path(self.contract), {"schema_version": 1, "status": "passed", "model_sha256": qa.digest(self.model),
                      "contract_sha256": qa.digest(self.contract), "inspector_sha256": qa.digest(qa.SCRIPTS / "inspect_model.py"),
                      "review_sha256": qa.digest(qa.review_path(self.contract)),
                      "checks": [{"name": name, "status": "passed"} for name in qa.expected_check_names(self.data)], "failures": []})

    def test_current_report_passes_and_same_size_model_edit_invalidates(self):
        self.passed_report()
        self.assertEqual(qa.acceptance_failures(self.contract), [])
        original_stat = self.model.stat()
        self.model.write_bytes(b"x" * original_stat.st_size)
        import os
        os.utime(self.model, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        self.assertTrue(any("model_sha256" in f for f in qa.acceptance_failures(self.contract)))

    def test_contract_preview_and_review_changes_invalidate_acceptance(self):
        for artifact in (self.contract, self.root / "overview.png", qa.review_path(self.contract)):
            self.passed_report()
            original = artifact.read_bytes()
            artifact.write_bytes(original + b" ")
            self.assertTrue(qa.acceptance_failures(self.contract))
            artifact.write_bytes(original)

    def test_empty_checks_and_false_pass_flag_are_rejected(self):
        self.passed_report()
        report = qa.read_json(qa.report_path(self.contract))
        report["checks"] = []
        qa.write_json(qa.report_path(self.contract), report)
        self.assertTrue(qa.acceptance_failures(self.contract))

    def test_sessions_are_isolated_and_paths_cannot_escape_root(self):
        qa.register(self.root, "chat-A", "job", self.contract)
        other = dict(self.payload, session_id="chat-B")
        self.assertEqual(qa.hook(self.root, other), {})
        self.assertEqual(qa.hook(self.root, dict(self.payload, cwd=str(self.root.parent))), {})
        self.assertNotEqual(qa.state_path(self.root, "../outside"), self.root.parent / "outside")
        with self.assertRaises(ValueError):
            qa.register(self.root / "narrow", "chat-A", "job", self.contract)

    def test_failure_continues_then_reports_without_infinite_loop(self):
        qa.register(self.root, "chat-A", "job", self.contract)
        replies = [qa.hook(self.root, self.payload) for _ in range(7)]
        self.assertEqual([r.get("decision") for r in replies[:3]], ["block"] * 3)
        self.assertIn("停止自动修复", replies[2]["reason"])
        self.assertNotIn("decision", replies[-1])
        state = qa.read_json(qa.state_path(self.root, "chat-A"))
        self.assertEqual(state["last_status"], "failed")
        self.assertLessEqual(state["repair_requests"], 3)
        qa.register(self.root, "chat-A", "job", self.contract)
        self.assertTrue(qa.read_json(qa.state_path(self.root, "chat-A"))["report_only_sent"])

    def test_progress_is_bounded_and_valid_model_can_finish(self):
        qa.register(self.root, "chat-A", "job", self.contract)
        with patch.object(qa, "acceptance_failures", side_effect=[["one"], ["two"], ["three"], ["four"]]):
            replies = [qa.hook(self.root, self.payload) for _ in range(4)]
        self.assertTrue(all(r.get("decision") == "block" for r in replies))
        self.assertIn("停止自动修复", replies[-1]["reason"])
        self.passed_report()
        self.assertEqual(qa.hook(self.root, self.payload), {})

    def test_interrupt_suspends_and_explicit_resume_preserves_budget(self):
        qa.register(self.root, "chat-A", "job", self.contract)
        qa.hook(self.root, self.payload)
        qa.hook(self.root, dict(self.payload, hook_event_name="Interrupt"))
        self.assertEqual(qa.hook(self.root, self.payload), {})
        with self.assertRaises(ValueError):
            qa.register(self.root, "chat-A", "job", self.contract)
        qa.register(self.root, "chat-A", "job", self.contract, resume=True)
        self.assertEqual(qa.read_json(qa.state_path(self.root, "chat-A"))["repair_requests"], 1)

    def test_no_registered_work_does_not_block_normal_chat(self):
        self.assertEqual(qa.hook(self.root, self.payload), {})
        context = qa.hook(self.root, dict(self.payload, hook_event_name="SessionStart"))
        self.assertIn("chat-A", context["hookSpecificOutput"]["additionalContext"])

    def test_installer_preserves_other_hooks_and_is_idempotent(self):
        path = self.root / ".codex/hooks.json"
        original = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other-check"}]}]}}
        qa.write_json(path, original)
        qa.install_hooks(self.root)
        first = qa.read_json(path)
        qa.install_hooks(self.root)
        self.assertEqual(qa.read_json(path), first)
        self.assertEqual(first["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
        self.assertEqual(len(first["hooks"]["Stop"]), 2)
        self.assertFalse((self.root / ".codex/hooks.trust.json").exists())

    def test_piping_contract_cannot_omit_system_checks(self):
        self.data["model_kind"] = "piping"
        qa.write_json(self.contract, self.data)
        with self.assertRaises(ValueError):
            qa.load_contract(self.contract)

    def test_installer_preserves_foreign_handlers_in_mixed_groups(self):
        path = self.root / ".codex/hooks.json"
        qa.write_json(path, {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "foreign-tool"},
            {"type": "command", "command": "old-qa", "statusMessage": "Model QA: Stop"}
        ]}]}})
        qa.install_hooks(self.root)
        handlers = [h for group in qa.read_json(path)["hooks"]["Stop"] for h in group["hooks"]]
        self.assertEqual(sum(h.get("command") == "foreign-tool" for h in handlers), 1)
        self.assertEqual(sum(h.get("statusMessage", "").startswith("Model QA:") for h in handlers), 1)

    def test_cli_hook_returns_single_json_object(self):
        result = subprocess.run([__import__('sys').executable, str(SCRIPT), "hook", "--root", str(self.root)],
                                input=json.dumps(self.payload), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})


if __name__ == "__main__":
    unittest.main()
