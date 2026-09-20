#!/usr/bin/env python3
"""Parse ComfyUI frontend JavaScript explicitly as native ES modules."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


MODULE_SUFFIXES = {".js", ".mjs"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def discover(root: Path, requested: list[Path] | None = None) -> tuple[list[Path], list[str]]:
    root = root.resolve()
    inputs = requested or [Path("web")]
    files: set[Path] = set()
    errors: list[str] = []
    for value in inputs:
        target = value if value.is_absolute() else root / value
        target = target.resolve()
        if not _inside(target, root):
            errors.append(f"path is outside plugin root: {target}")
            continue
        if target.is_file():
            if target.suffix.casefold() not in MODULE_SUFFIXES:
                errors.append(f"not a JavaScript module: {target}")
            else:
                files.add(target)
            continue
        if target.is_dir():
            for candidate in target.rglob("*"):
                if (
                    candidate.is_file()
                    and candidate.suffix.casefold() in MODULE_SUFFIXES
                    and "node_modules" not in candidate.relative_to(root).parts
                ):
                    files.add(candidate.resolve())
            continue
        errors.append(f"path does not exist: {target}")
    return sorted(files), errors


def check(root: Path, requested: list[Path] | None = None, node: str | None = None) -> dict[str, object]:
    root = root.resolve()
    executable = node or shutil.which("node")
    result: dict[str, object] = {
        "root": str(root),
        "mode": "explicit-esm-parse",
        "node": executable,
    }
    if not executable:
        return {**result, "status": "error", "errors": ["Node.js executable was not found"]}

    files, errors = discover(root, requested)
    if not files:
        errors.append("no JavaScript modules found")
    failures: list[dict[str, str]] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            failures.append({"path": str(path), "error": f"read failed: {exc}"})
            continue
        completed = subprocess.run(
            [executable, "--check", "--input-type=module"],
            input=source.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            raw_detail = completed.stderr or completed.stdout
            detail = raw_detail.decode("utf-8", errors="replace").strip() if raw_detail else "ESM parse failed"
            failures.append({"path": str(path), "error": detail})

    result.update(
        {
            "status": "passed" if not errors and not failures else "error",
            "checked": len(files),
            "files": [str(path) for path in files],
            "failures": failures,
        }
    )
    if errors:
        result["errors"] = errors
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="ComfyUI plugin root")
    parser.add_argument("--node", help="Node.js executable; defaults to PATH lookup")
    parser.add_argument("paths", nargs="*", type=Path, help="Files/directories relative to the plugin root")
    args = parser.parse_args()
    result = check(args.root, args.paths or None, args.node)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
