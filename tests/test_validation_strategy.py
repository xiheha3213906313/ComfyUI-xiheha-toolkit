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
    / "set_validation_strategy.py"
)
SPEC = importlib.util.spec_from_file_location("set_validation_strategy", SCRIPT_PATH)
STRATEGY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(STRATEGY)


class ValidationStrategyTests(unittest.TestCase):
    NOW = datetime(2026, 9, 19, 16, 48, tzinfo=timezone(timedelta(hours=8)))

    def test_adds_configuration_without_changing_profile_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "COMFYUI_PLUGIN_PROJECT.md"
            profile.write_text(
                "---\nprofile_schema: comfyui-plugin-project/v1\nprofile_status: complete\n"
                "analyzed_at: 2026-09-19T12:00:00+08:00\n---\n\n# Project\nBody\n",
                encoding="utf-8",
            )
            result = STRATEGY.update(root, "medium", "model-a", self.NOW)
            content = profile.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "updated")
        self.assertIn("validation_level: medium", content)
        self.assertIn("validation_model: model-a", content)
        self.assertTrue(content.endswith("# Project\nBody\n"))

    def test_replaces_existing_configuration_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "COMFYUI_PLUGIN_PROJECT.md"
            profile.write_text(
                "---\nprofile_schema: comfyui-plugin-project/v1\nprofile_status: complete\n"
                "analyzed_at: 2026-09-19T12:00:00+08:00\nvalidation_level: careful\n"
                "validation_model: old-model\nvalidation_configured_at: 2026-09-01T12:00:00+08:00\n"
                "---\n\n# Project\n",
                encoding="utf-8",
            )
            STRATEGY.update(root, "simple", "new-model", self.NOW)
            content = profile.read_text(encoding="utf-8")

        self.assertEqual(content.count("validation_level:"), 1)
        self.assertIn("validation_level: simple", content)
        self.assertIn("validation_model: new-model", content)

    def test_level_only_change_preserves_existing_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "COMFYUI_PLUGIN_PROJECT.md"
            profile.write_text(
                "---\nprofile_schema: comfyui-plugin-project/v1\nprofile_status: complete\n"
                "analyzed_at: 2026-09-19T12:00:00+08:00\nvalidation_level: careful\n"
                "validation_model: bound-model\nvalidation_configured_at: 2026-09-01T12:00:00+08:00\n"
                "---\n\n# Project\n",
                encoding="utf-8",
            )
            result = STRATEGY.update(root, "simple", None, self.NOW)
            content = profile.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["validation_model"], "bound-model")
        self.assertIn("validation_level: simple", content)
        self.assertIn("validation_model: bound-model", content)

    def test_new_configuration_requires_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "COMFYUI_PLUGIN_PROJECT.md"
            profile.write_text(
                "---\nprofile_schema: comfyui-plugin-project/v1\nprofile_status: complete\n"
                "analyzed_at: 2026-09-19T12:00:00+08:00\nvalidation_model: null\n"
                "---\n\n# Project\n",
                encoding="utf-8",
            )
            result = STRATEGY.update(root, "simple", None, self.NOW)

        self.assertEqual(result["status"], "error")
        self.assertIn("--model is required", result["error"])

    def test_missing_profile_returns_error(self):
        with tempfile.TemporaryDirectory() as temp:
            result = STRATEGY.update(Path(temp), "simple", "model-a", self.NOW)
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
