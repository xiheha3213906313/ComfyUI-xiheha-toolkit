from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


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


class SkillValidationToolTests(unittest.TestCase):
    def _make_tree(self, root: Path) -> tuple[Path, Path]:
        comfy = root / "ComfyUI"
        plugin = comfy / "custom_nodes" / "demo-plugin"
        plugin.mkdir(parents=True)
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

    def test_controlled_import_handles_hyphen_and_idempotent_route(self):
        with tempfile.TemporaryDirectory() as temp:
            comfy, plugin = self._make_tree(Path(temp))
            result = IMPORT_CHECK.check(plugin)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(Path(result["comfy_root"]), comfy)
        self.assertEqual(result["registration_style"], "classic")
        self.assertEqual(result["registration"]["node_ids"], ["Demo"])
        self.assertEqual(result["routes"][0]["path"], "/demo")
        self.assertTrue(result["repeat_import_idempotent"])
        self.assertEqual(result["captured_stdout"].count("controlled import output"), 2)

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

    def test_controlled_import_reports_unresolved_comfy_root(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin = Path(temp) / "standalone-plugin"
            plugin.mkdir()
            (plugin / "__init__.py").write_text("NODE_CLASS_MAPPINGS = {}\n", encoding="utf-8")
            result = IMPORT_CHECK.check(plugin)
        self.assertEqual(result["status"], "error")
        self.assertIn("--comfy-root", result["error"])


if __name__ == "__main__":
    unittest.main()
