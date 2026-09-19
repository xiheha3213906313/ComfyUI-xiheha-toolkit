#!/usr/bin/env python3
"""Preflight Python and path resolution for a ComfyUI custom-node plugin."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def infer_comfy_root(plugin_root: Path) -> Path | None:
    plugin_root = plugin_root.resolve()
    if plugin_root.parent.name.casefold() == "custom_nodes":
        return plugin_root.parent.parent
    for parent in plugin_root.parents:
        if (parent / "folder_paths.py").is_file() and (parent / "custom_nodes").is_dir():
            return parent
    return None


def inspect(plugin_root: Path, comfy_root: Path | None = None) -> dict[str, object]:
    plugin_root = plugin_root.resolve()
    comfy_root = comfy_root.resolve() if comfy_root else infer_comfy_root(plugin_root)
    result: dict[str, object] = {
        "python": sys.executable,
        "working_directory": os.getcwd(),
        "plugin_root": str(plugin_root),
        "comfy_root": str(comfy_root) if comfy_root else None,
        "plugin_init": str(plugin_root / "__init__.py"),
    }
    errors: list[str] = []
    if not plugin_root.is_dir():
        errors.append("plugin root is not a directory")
    if not (plugin_root / "__init__.py").is_file():
        errors.append("plugin root has no __init__.py")
    if comfy_root is None or not comfy_root.is_dir():
        errors.append("ComfyUI root could not be resolved")
        result.update({"status": "error", "errors": errors})
        return result

    saved_path = list(sys.path)
    saved_folder_paths = sys.modules.pop("folder_paths", None)
    try:
        sys.path[:] = [str(comfy_root), *[entry for entry in saved_path if Path(entry or os.getcwd()).resolve() != plugin_root]]
        importlib.invalidate_caches()
        module = importlib.import_module("folder_paths")
        origin = Path(module.__file__).resolve() if getattr(module, "__file__", None) else None
        result["folder_paths"] = str(origin) if origin else None
        if origin is None or not _inside(origin, comfy_root):
            errors.append("folder_paths did not resolve from the selected ComfyUI root")
    except Exception as exc:  # Preflight must report third-party import failures.
        result["folder_paths"] = None
        errors.append(f"folder_paths import failed: {type(exc).__name__}: {exc}")
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("folder_paths", None)
        if saved_folder_paths is not None:
            sys.modules["folder_paths"] = saved_folder_paths

    python = str(Path(sys.executable).resolve())
    result["recommended"] = {
        "working_directory": str(plugin_root),
        "environment": {"PYTHONPATH": str(comfy_root)},
        "unittest": f'"{python}" -m unittest discover -s tests',
        "controlled_import": (
            f'"{python}" <skill-dir>/scripts/check_plugin_import.py '
            f'--root "{plugin_root}" --comfy-root "{comfy_root}"'
        ),
    }
    result["status"] = "ready" if not errors else "error"
    if errors:
        result["errors"] = errors
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        "--plugin-root",
        dest="plugin_root",
        type=Path,
        default=Path.cwd(),
        help="Plugin root; --plugin-root remains a compatibility alias",
    )
    parser.add_argument("--comfy-root", type=Path, help="ComfyUI root; inferred from a standard custom_nodes layout")
    args = parser.parse_args()
    result = inspect(args.plugin_root, args.comfy_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
