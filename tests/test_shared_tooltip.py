"""Runtime-backed tests for the split Tooltip parser and stylesheet layout."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestSharedTooltipModule(unittest.TestCase):
    def test_tooltip_parser_module_executes_and_escapes_content(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for Tooltip module tests")
        uri = (ROOT / "web" / "shared" / "tooltip" / "data.js").as_uri()
        script = f"""
            import {{ parseTooltipString, renderTooltipContent, resolveTooltipData }} from {uri!r};
            const parsed = parseTooltipString('【镜头检测】\\n说明\\n• 阈值：0.5', 'fallback');
            if (parsed.title !== '镜头检测' || parsed.desc !== '说明' || parsed.details[0] !== '阈值：0.5') throw new Error('parse failed');
            const resolved = resolveTooltipData({{ name: 'format', tooltip: '[格式]\\n原生说明' }});
            if (resolved.title !== '格式' || resolved.desc !== '原生说明') throw new Error('resolve failed');
            const html = renderTooltipContent({{ title: '<script>', badge: '参数', desc: '<img>', details: ['<b>bad</b>'] }});
            if (html.includes('<script>') || html.includes('<img>') || html.includes('<b>bad</b>')) throw new Error('unescaped content');
        """
        result = subprocess.run(
            [node, "--input-type=module", "--eval", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_is_instance_scoped_and_facade_is_stable(self):
        facade = (ROOT / "web" / "shared" / "tooltip.js").read_text(encoding="utf-8")
        runtime = (ROOT / "web" / "shared" / "tooltip" / "runtime.js").read_text(encoding="utf-8")
        self.assertIn("registerCustomTooltip", facade)
        self.assertIn("registeredNodes.get(node)", runtime)
        self.assertIn("if (!config?.enabled", runtime)
        self.assertIn("for (const widget of node.widgets)", runtime)
        self.assertIn("passive: true", runtime)
        self.assertNotIn("stopPropagation", runtime)
        self.assertNotIn("preventDefault", runtime)

    def test_tooltip_stylesheet_is_lazy_and_separate(self):
        stylesheets = (ROOT / "web" / "shared" / "stylesheets.js").read_text(encoding="utf-8")
        manifest = (ROOT / "web" / "toolkit.css").read_text(encoding="utf-8")
        tooltip_css = ROOT / "web" / "styles" / "tooltip.css"
        self.assertTrue(tooltip_css.is_file())
        self.assertIn("xh-tooltip-stylesheet", stylesheets)
        self.assertIn("../styles/tooltip.css", stylesheets)
        self.assertNotIn("tooltip.css", manifest)


if __name__ == "__main__":
    unittest.main()
