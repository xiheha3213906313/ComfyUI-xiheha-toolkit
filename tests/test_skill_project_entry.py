from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "comfyui-plugin-development"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "ensure_project_agents.py"
SPEC = importlib.util.spec_from_file_location("ensure_project_agents", SCRIPT_PATH)
PROJECT_ENTRY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PROJECT_ENTRY)


class ProjectEntryTests(unittest.TestCase):
    def test_creates_minimal_agents_from_skill_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = PROJECT_ENTRY.ensure(root)
            content = (root / "AGENTS.md").read_text(encoding="utf-8")

        expected = (SKILL_ROOT / "assets" / "AGENTS.md").read_text(encoding="utf-8-sig")
        self.assertEqual(result["status"], "created")
        self.assertEqual(content, expected)

    def test_existing_agents_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "AGENTS.md"
            target.write_text("user guidance\n", encoding="utf-8")
            result = PROJECT_ENTRY.ensure(root)

            self.assertEqual(result["status"], "existing")
            self.assertEqual(target.read_text(encoding="utf-8"), "user guidance\n")

    def test_override_prevents_competing_agents_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "AGENTS.override.md").write_text("override\n", encoding="utf-8")
            result = PROJECT_ENTRY.ensure(root)

            self.assertEqual(result["status"], "skipped_alternative")
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertEqual(result["alternatives"], ["AGENTS.override.md"])

    def test_common_fallback_prevents_competing_agents_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "TEAM_GUIDE.md").write_text("team guidance\n", encoding="utf-8")
            result = PROJECT_ENTRY.ensure(root)

            self.assertEqual(result["status"], "skipped_alternative")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_nonexistent_root_returns_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing"
            result = PROJECT_ENTRY.ensure(root)

        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
