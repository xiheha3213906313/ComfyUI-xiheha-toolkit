#!/usr/bin/env python3
"""Run a ComfyUI plugin's unittest suite with portable import paths."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def infer_comfy_root(plugin_root: Path) -> Path | None:
    plugin_root = plugin_root.resolve()
    if plugin_root.parent.name.casefold() == "custom_nodes":
        candidate = plugin_root.parent.parent
        if (candidate / "folder_paths.py").is_file():
            return candidate
    for parent in plugin_root.parents:
        if (parent / "folder_paths.py").is_file() and (parent / "custom_nodes").is_dir():
            return parent
    return None


def build_environment(plugin_root: Path, comfy_root: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(base if base is not None else os.environ)
    paths = [str(comfy_root.resolve()), str(plugin_root.resolve())]
    existing = environment.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def run(
    plugin_root: Path,
    comfy_root: Path | None = None,
    python: str | None = None,
    start_directory: str = "tests",
    pattern: str = "test*.py",
) -> int:
    plugin_root = plugin_root.resolve()
    comfy_root = comfy_root.resolve() if comfy_root else infer_comfy_root(plugin_root)
    if not (plugin_root / "__init__.py").is_file():
        print("error: plugin root has no __init__.py", file=sys.stderr)
        return 2
    if comfy_root is None or not (comfy_root / "folder_paths.py").is_file():
        print("error: ComfyUI root could not be resolved; pass --comfy-root", file=sys.stderr)
        return 2
    if not (plugin_root / start_directory).is_dir():
        print(f"error: unittest start directory does not exist: {start_directory}", file=sys.stderr)
        return 2

    executable = python or sys.executable
    command = [
        executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        start_directory,
        "-p",
        pattern,
    ]
    print(f"working_directory: {plugin_root}", file=sys.stderr)
    print(f"comfy_root: {comfy_root}", file=sys.stderr)
    print(f"python: {executable}", file=sys.stderr)
    completed = subprocess.run(
        command,
        cwd=plugin_root,
        env=build_environment(plugin_root, comfy_root),
        check=False,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="ComfyUI plugin root")
    parser.add_argument("--comfy-root", type=Path, help="ComfyUI root; inferred from standard layout")
    parser.add_argument("--python", help="Python executable; defaults to the interpreter running this script")
    parser.add_argument("--start-directory", default="tests")
    parser.add_argument("--pattern", default="test*.py")
    args = parser.parse_args()
    return run(args.root, args.comfy_root, args.python, args.start_directory, args.pattern)


if __name__ == "__main__":
    raise SystemExit(main())
