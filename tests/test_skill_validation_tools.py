from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "comfyui-plugin-development" / "scripts"


def load_script(name: str):
    path = SKILL_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ENVIRONMENT = load_script("validate_environment")
IMPORT_CHECK = load_script("check_plugin_import")
FRONTEND_CHECK = load_script("check_frontend_syntax")
TEST_RUNNER = load_script("run_plugin_tests")


class SkillValidationToolTests(unittest.TestCase):
    def _make_tree(self, root: Path) -> tuple[Path, Path]:
        comfy = root / "ComfyUI"
        plugin = comfy / "custom_nodes" / "demo-plugin"
        plugin.mkdir(parents=True)
        (plugin / "web").mkdir()
        (comfy / "folder_paths.py").write_text("VALUE = 'fake-comfy'\n", encoding="utf-8")
        (comfy / "server.py").write_text(
            "class PromptServer:\n    instance = None\n",
            encoding="utf-8",
        )
        (plugin / "routes.py").write_text(
            "from server import PromptServer\n"
            "_REGISTERED = False\n"
            "def register():\n"
            "    global _REGISTERED\n"
            "    if _REGISTERED:\n"
            "        return\n"
            "    @PromptServer.instance.routes.post('/demo')\n"
            "    def demo(request):\n"
            "        return request\n"
            "    _REGISTERED = True\n",
            encoding="utf-8",
        )
        (plugin / "__init__.py").write_text(
            "from .routes import register\n"
            "print('controlled import output')\n"
            "NODE_CLASS_MAPPINGS = {'Demo': object}\n"
            "NODE_DISPLAY_NAME_MAPPINGS = {'Demo': 'Demo'}\n"
            "WEB_DIRECTORY = './web'\n"
            "register()\n",
            encoding="utf-8",
        )
        return comfy, plugin

    def test_environment_preflight_resolves_fake_comfy_root(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            result = ENVIRONMENT.inspect(plugin)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(Path(result["comfy_root"]), comfy)
        self.assertTrue(str(result["folder_paths"]).endswith("folder_paths.py"))
        self.assertIn("run_plugin_tests.py", result["recommended"]["unittest_wrapper"])
        self.assertIn("check_frontend_syntax.py", result["recommended"]["frontend_syntax"])

    def test_controlled_import_handles_hyphen_and_idempotent_route(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            result = IMPORT_CHECK.check(plugin)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(Path(result["comfy_root"]), comfy)
        self.assertEqual(result["registration_style"], "classic")
        self.assertEqual(result["registration"]["node_ids"], ["Demo"])
        self.assertEqual(result["routes"][0]["path"], "/demo")
        self.assertTrue(result["repeat_execution_route_stable"])
        self.assertEqual(result["evidence_scope"], "classic-registration-structure")
        self.assertTrue(result["web_directory_exists"])
        self.assertEqual(result["captured_stdout"].count("controlled import output"), 2)

    def test_controlled_import_marks_new_registration_surface_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            (plugin / "__init__.py").write_text(
                "NODE_LIST = []\n",
                encoding="utf-8",
            )
            result = IMPORT_CHECK.check(plugin, comfy)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["registration_style"], "node-list")
        self.assertEqual(result["evidence_scope"], "registration-surface-only")
        self.assertTrue(result["limitations"])

    def test_controlled_import_reports_duplicate_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            (plugin / "__init__.py").write_text(
                "from server import PromptServer\n"
                "NODE_CLASS_MAPPINGS = {'Demo': object}\n"
                "@PromptServer.instance.routes.post('/duplicate')\n"
                "def duplicate(request):\n"
                "    return request\n",
                encoding="utf-8",
            )
            result = IMPORT_CHECK.check(plugin, comfy)
        self.assertEqual(result["status"], "error")
        self.assertIn("duplicate routes", result["error"])
        self.assertEqual(result["phase"], "reexecute-plugin-root")

    def test_controlled_import_reports_unresolved_comfy_root(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin = Path(temp) / "standalone-plugin"
            plugin.mkdir()
            (plugin / "__init__.py").write_text("NODE_CLASS_MAPPINGS = {}\n", encoding="utf-8")
            result = IMPORT_CHECK.check(plugin)
        self.assertEqual(result["status"], "error")
        self.assertIn("--comfy-root", result["error"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for explicit ESM parsing")
    def test_frontend_check_uses_esm_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "valid.js").write_text(
                'import value from "./not-resolved.js";\nexport const result = `⚠️ ${value}`;\n',
                encoding="utf-8",
            )
            passed = FRONTEND_CHECK.check(root)
            (web / "duplicate.js").write_text(
                "export const FLAG = false;\nexport const FLAG = true;\n",
                encoding="utf-8",
            )
            failed = FRONTEND_CHECK.check(root)

        self.assertEqual(passed["status"], "passed")
        self.assertEqual(passed["checked"], 1)
        self.assertEqual(failed["status"], "error")
        self.assertIn("already been declared", failed["failures"][0]["error"])

    def test_unittest_runner_builds_portable_child_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            (plugin / "tests").mkdir()
            with patch.object(
                TEST_RUNNER.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ) as mocked:
                returncode = TEST_RUNNER.run(plugin, python="python-test")

        self.assertEqual(returncode, 0)
        command = mocked.call_args.args[0]
        options = mocked.call_args.kwargs
        self.assertEqual(command[:4], ["python-test", "-m", "unittest", "discover"])
        self.assertEqual(options["cwd"], plugin.resolve())
        python_paths = options["env"]["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(python_paths[:2], [str(comfy.resolve()), str(plugin.resolve())])


if __name__ == "__main__":
    unittest.main()
