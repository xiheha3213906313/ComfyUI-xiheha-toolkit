from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "comfyui-plugin-development"
    / "scripts"
    / "check_project_profile.py"
)
SPEC = importlib.util.spec_from_file_location("check_project_profile", SCRIPT_PATH)
PROFILE_CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PROFILE_CHECKER)


class ProjectProfileCheckerTests(unittest.TestCase):
    TZ = timezone(timedelta(hours=8))

    def _write_profile(self, root: Path, frontmatter: str) -> None:
        (root / "COMFYUI_PLUGIN_PROJECT.md").write_text(
            f"---\n{frontmatter.strip()}\n---\n\n# Profile\n",
            encoding="utf-8",
        )

    def test_missing_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            result = PROFILE_CHECKER.inspect(
                Path(temp),
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                current_agent="Codex",
            )
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["question_tool"]["preferred_tool"], "request_user_input")
        self.assertTrue(result["question_tool"]["availability_must_be_checked"])

    def test_known_agent_question_tool_mappings(self):
        cases = {
            "Codex": "request_user_input",
            "Claude Code": "AskUserQuestion",
            "Antigravity": "ask_question",
            "Cursor": "AskQuestion",
            "GitHub Copilot": "ask_user",
            "OpenCode": "question",
            "workbuddy": "AskUserQuestion",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for agent, expected in cases.items():
                with self.subTest(agent=agent):
                    result = PROFILE_CHECKER.inspect(
                        root,
                        datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                        current_agent=agent,
                    )
                    self.assertEqual(result["question_tool"]["preferred_tool"], expected)
                    self.assertEqual(result["question_tool"]["match"], "known_agent")

    def test_configured_agent_is_only_a_fallback_hint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: complete
analyzed_at: 2026-09-19T12:00:00+08:00
validation_level: medium
validation_model: model-a
validation_agent: Cursor
validation_configured_at: 2026-09-19T12:00:00+08:00
""",
            )
            hinted = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 19, 12, tzinfo=self.TZ))
            overridden = PROFILE_CHECKER.inspect(
                root,
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                current_agent="Claude Code",
            )

        self.assertEqual(hinted["question_tool"]["candidate_source"], "configured_agent_hint")
        self.assertEqual(hinted["question_tool"]["preferred_tool"], "AskQuestion")
        self.assertEqual(overridden["question_tool"]["candidate_source"], "current_agent")
        self.assertEqual(overridden["question_tool"]["preferred_tool"], "AskUserQuestion")

    def test_complete_profile_is_ready_and_reports_missing_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: complete
analyzed_at: 2026-09-19T12:00:00+08:00
""",
            )
            result = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 19, 12, tzinfo=self.TZ))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["profile_status"], "complete")
        self.assertEqual(result["validation"]["status"], "missing")
        self.assertEqual(result["validation"]["action"], "choose_validation_strategy")
        self.assertIs(result["validation"]["blocking"], True)

    def test_partial_profile_reports_partial_top_level_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: partial
analyzed_at: 2026-09-19T12:00:00+08:00
""",
            )
            result = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 19, 12, tzinfo=self.TZ))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["profile_status"], "partial")

    def test_validation_model_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: complete
analyzed_at: 2026-09-19T12:00:00+08:00
validation_level: simple
validation_model: strong-model-v1
validation_agent: Codex
validation_configured_at: 2026-09-19T12:00:00+08:00
""",
            )
            matched = PROFILE_CHECKER.inspect(
                root,
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                "strong-model-v1",
            )
            mismatched = PROFILE_CHECKER.inspect(
                root,
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                "other-model",
            )
            unknown_current = PROFILE_CHECKER.inspect(
                root,
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
            )
        self.assertIs(matched["validation"]["model_match"], True)
        self.assertEqual(matched["validation"]["action"], "continue")
        self.assertIs(matched["validation"]["blocking"], False)
        self.assertIs(matched["validation"]["model_confirmation_required"], False)
        self.assertIs(mismatched["validation"]["model_match"], False)
        self.assertEqual(mismatched["validation"]["action"], "confirm_validation_strategy")
        self.assertIs(mismatched["validation"]["blocking"], True)
        self.assertIs(unknown_current["validation"]["model_match"], None)
        self.assertIs(unknown_current["validation"]["model_confirmation_required"], True)
        self.assertEqual(unknown_current["validation"]["reason"], "current_model_unavailable")

    def test_json_quoted_model_label_round_trips(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: complete
analyzed_at: 2026-09-19T12:00:00+08:00
validation_level: medium
validation_model: "Model #1: High"
validation_configured_at: 2026-09-19T12:00:00+08:00
""",
            )
            result = PROFILE_CHECKER.inspect(
                root,
                datetime(2026, 9, 19, 12, tzinfo=self.TZ),
                "Model #1: High",
            )
        self.assertIs(result["validation"]["model_match"], True)

    def test_declined_profile_waits_until_reminder_date(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: declined
declined_at: 2026-09-19T12:00:00+08:00
remind_after: 2026-09-22T12:00:00+08:00
""",
            )
            before = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 22, 11, 59, tzinfo=self.TZ))
            due = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 22, 12, tzinfo=self.TZ))
        self.assertEqual(before["status"], "declined")
        self.assertEqual(due["status"], "reminder_due")

    def test_declined_profile_requires_both_dates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: comfyui-plugin-project/v1
profile_status: declined
declined_at: 2026-09-19T12:00:00+08:00
remind_after: null
""",
            )
            result = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 22, 12, tzinfo=self.TZ))
        self.assertEqual(result["status"], "invalid")

    def test_unknown_schema_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_profile(
                root,
                """
profile_schema: other/v1
profile_status: complete
analyzed_at: 2026-09-19T12:00:00+08:00
""",
            )
            result = PROFILE_CHECKER.inspect(root, datetime(2026, 9, 19, 12, tzinfo=self.TZ))
        self.assertEqual(result["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
