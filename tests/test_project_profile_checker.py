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
            result = PROFILE_CHECKER.inspect(Path(temp), datetime(2026, 9, 19, 12, tzinfo=self.TZ))
        self.assertEqual(result["status"], "missing")

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
        self.assertIs(matched["validation"]["model_confirmation_required"], False)
        self.assertIs(mismatched["validation"]["model_match"], False)
        self.assertIs(unknown_current["validation"]["model_match"], None)
        self.assertIs(unknown_current["validation"]["model_confirmation_required"], True)

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
