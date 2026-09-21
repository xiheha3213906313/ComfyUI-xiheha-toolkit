"""Run real ESM unit tests for pure frontend modules."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendModuleTests(unittest.TestCase):
    def test_node_frontend_modules(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for frontend module tests")
        tests = sorted((ROOT / "tests" / "frontend").glob("*.test.mjs"))
        result = subprocess.run(
            [node, "--test", *map(str, tests)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))


if __name__ == "__main__":
    unittest.main()
