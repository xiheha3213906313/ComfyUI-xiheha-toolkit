# Unit and integration tests for web/shared/tooltip.js
import os
import unittest
import re


class TestSharedTooltipModule(unittest.TestCase):
    """Verify generic shared tooltip engine, Python string parser, and strict node isolation."""

    def setUp(self):
        self.tooltip_js_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "web", "shared", "tooltip.js")
        )
        self.assertTrue(os.path.isfile(self.tooltip_js_path), "web/shared/tooltip.js must exist")
        with open(self.tooltip_js_path, "r", encoding="utf-8") as f:
            self.js_content = f.read()

    def test_exports_and_public_api(self):
        """Verify all required generic APIs are exported."""
        required_exports = [
            "export function registerCustomTooltip",
            "export function unregisterCustomTooltip",
            "export function updateTooltipMutualExclusion",
            "export function parseTooltipString",
            "export function resolveTooltipData",
            "export function getWidgetAtPos",
            "export function showTooltip",
            "export function hideTooltip",
            "export function ensureGlobalListeners",
            "export function ensureTooltipStylesheet",
        ]
        for item in required_exports:
            self.assertIn(item, self.js_content, f"Missing export in web/shared/tooltip.js: {item}")

    def test_python_tooltip_parser_logic(self):
        """Verify parsing patterns for Python multi-line tooltip strings."""
        # 1. Bracket extraction
        self.assertIn("match(/^【(.*?)】/)", self.js_content)
        self.assertIn("match(/^\\[(.*?)\\]/)", self.js_content)

        # 2. Bullet point handling
        self.assertIn("startsWith(\"•\")", self.js_content)
        self.assertIn("startsWith(\"-\")", self.js_content)
        self.assertIn("startsWith(\"*\")", self.js_content)

        # 3. Colon bolding
        self.assertIn("indexOf(\"：\")", self.js_content)
        self.assertIn("<b>", self.js_content)

    def test_strict_isolation_guarantees(self):
        """Verify that external nodes cannot be intercepted or modified."""
        # Must check registeredNodes map
        self.assertIn("registeredNodes.get(node)", self.js_content)
        self.assertIn("if (!config || !config.enabled)", self.js_content,
                      "Must immediately return null for unregistered or disabled nodes")

        # Mutual exclusion must be strictly scoped to node.widgets
        self.assertIn("for (const w of node.widgets)", self.js_content)
        self.assertIn("w.__xhOrigTooltip", self.js_content)
        self.assertIn("w.tooltip = null", self.js_content)
        self.assertIn("w.tooltip = w.__xhOrigTooltip", self.js_content)

        # Passive/capture listeners to not interfere with standard event propagation
        self.assertIn("passive: true", self.js_content)
        self.assertNotIn("e.stopPropagation()", self.js_content, "Must never block ComfyUI event propagation")
        self.assertNotIn("e.preventDefault()", self.js_content, "Must never prevent default ComfyUI behavior")

    def test_dynamic_stylesheet_linkage(self):
        """Verify lazy loading of standalone web/tooltip.css."""
        self.assertIn("xh-tooltip-stylesheet", self.js_content)
        self.assertIn("../tooltip.css", self.js_content)

    def test_smart_video_splitter_delegates_to_shared_tooltip(self):
        """Verify smart-video-splitter.js uses the shared module while maintaining backward compatibility."""
        splitter_js_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "web", "nodes", "smart-video-splitter.js")
        )
        with open(splitter_js_path, "r", encoding="utf-8") as f:
            splitter_content = f.read()

        self.assertIn('from "../shared/tooltip.js"', splitter_content)
        self.assertIn("registerCustomTooltip(node", splitter_content)
        self.assertIn("export const ENABLE_CUSTOM_TOOLTIP = false", splitter_content)
        self.assertIn("export function applyTooltipMutualExclusion", splitter_content)


if __name__ == "__main__":
    unittest.main()
