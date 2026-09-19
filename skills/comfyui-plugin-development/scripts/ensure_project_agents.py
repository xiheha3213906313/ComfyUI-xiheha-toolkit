#!/usr/bin/env python3
"""Create the skill's minimal AGENTS.md without overwriting project guidance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ENTRY_NAME = "AGENTS.md"
ALTERNATIVE_NAMES = ("AGENTS.override.md", "TEAM_GUIDE.md", ".agents.md")
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / ENTRY_NAME


def ensure(root: Path) -> dict[str, object]:
    root = root.resolve()
    target = root / ENTRY_NAME
    result: dict[str, object] = {"path": str(target)}

    if not root.is_dir():
        return {**result, "status": "error", "error": "plugin root is not a directory"}
    if target.exists() or target.is_symlink():
        return {**result, "status": "existing"}

    alternatives = [name for name in ALTERNATIVE_NAMES if (root / name).exists()]
    if alternatives:
        return {
            **result,
            "status": "skipped_alternative",
            "alternatives": alternatives,
        }

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8-sig")
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(template)
    except FileExistsError:
        return {**result, "status": "existing"}
    except (OSError, UnicodeError) as exc:
        return {**result, "status": "error", "error": str(exc)}
    return {**result, "status": "created", "template": str(TEMPLATE_PATH)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="ComfyUI plugin root")
    args = parser.parse_args()
    result = ensure(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
