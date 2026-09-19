#!/usr/bin/env python3
"""Controlled import check for a ComfyUI custom-node plugin."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


class RouteCollector:
    def __init__(self) -> None:
        self.registrations: list[dict[str, str]] = []

    def __getattr__(self, method: str):
        def register(path: str, *args: object, **kwargs: object):  # noqa: ARG001
            def decorate(function):
                self.registrations.append(
                    {"method": method.upper(), "path": str(path), "handler": function.__name__}
                )
                return function

            return decorate

        return register


class PromptServerStub:
    def __init__(self) -> None:
        self.routes = RouteCollector()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


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


def _registration_summary(module: ModuleType) -> tuple[str, dict[str, object]]:
    mappings = getattr(module, "NODE_CLASS_MAPPINGS", None)
    node_list = getattr(module, "NODE_LIST", None)
    entrypoint = getattr(module, "comfy_entrypoint", None)
    if isinstance(mappings, dict):
        display = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", None)
        if display is not None and not isinstance(display, dict):
            raise TypeError("NODE_DISPLAY_NAME_MAPPINGS must be a dict when present")
        unknown_display = sorted(set(display or {}) - set(mappings))
        if unknown_display:
            raise ValueError(f"display mappings contain unknown node IDs: {unknown_display}")
        return "classic", {
            "node_ids": sorted(str(key) for key in mappings),
            "display_mapping_present": isinstance(display, dict),
        }
    if node_list is not None:
        return "node-list", {"node_list_type": type(node_list).__name__}
    if callable(entrypoint):
        return "entrypoint", {"entrypoint": getattr(entrypoint, "__name__", "comfy_entrypoint")}
    raise ValueError("no supported node registration surface found")


def check(plugin_root: Path, comfy_root: Path | None = None) -> dict[str, object]:
    plugin_root = plugin_root.resolve()
    comfy_root = comfy_root.resolve() if comfy_root else infer_comfy_root(plugin_root)
    result: dict[str, object] = {
        "mode": "controlled",
        "plugin_root": str(plugin_root),
        "comfy_root": str(comfy_root) if comfy_root else None,
        "real_comfyui_startup": False,
    }
    if not (plugin_root / "__init__.py").is_file():
        return {**result, "status": "error", "error": "plugin root has no __init__.py"}
    if comfy_root is None:
        return {**result, "status": "error", "error": "ComfyUI root could not be resolved; pass --comfy-root"}
    if not (comfy_root / "folder_paths.py").is_file():
        return {**result, "status": "error", "error": "selected ComfyUI root has no folder_paths.py"}

    module_name = "_comfy_plugin_check_" + hashlib.sha256(str(plugin_root).encode()).hexdigest()[:12]
    saved_path = list(sys.path)
    saved_server = sys.modules.pop("server", None)
    saved_folder_paths = sys.modules.pop("folder_paths", None)
    saved_plugin_modules = {key: value for key, value in sys.modules.items() if key == module_name or key.startswith(module_name + ".")}
    for key in saved_plugin_modules:
        sys.modules.pop(key, None)

    server_module: ModuleType | None = None
    original_instance: Any = None
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        excluded = {plugin_root, plugin_root.parent}
        remainder = []
        for entry in saved_path:
            resolved = Path(entry or os.getcwd()).resolve()
            if resolved not in excluded and resolved != comfy_root:
                remainder.append(entry)
        sys.path[:] = [str(comfy_root), str(plugin_root.parent), *remainder]
        importlib.invalidate_caches()
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            server_module = importlib.import_module("server")
            server_origin = Path(server_module.__file__).resolve() if getattr(server_module, "__file__", None) else None
            if server_origin is None or not _inside(server_origin, comfy_root):
                raise ImportError("server did not resolve from the selected ComfyUI root")
            prompt_server = getattr(server_module, "PromptServer", None)
            if prompt_server is None:
                raise ImportError("ComfyUI server module has no PromptServer")
            original_instance = getattr(prompt_server, "instance", None)
            stub = PromptServerStub()
            prompt_server.instance = stub

            spec = importlib.util.spec_from_file_location(
                module_name,
                plugin_root / "__init__.py",
                submodule_search_locations=[str(plugin_root)],
            )
            if spec is None or spec.loader is None:
                raise ImportError("could not create plugin import spec")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            style, registration = _registration_summary(module)
            first_routes = list(stub.routes.registrations)

            spec.loader.exec_module(module)
            second_routes = list(stub.routes.registrations)
        if second_routes != first_routes:
            raise RuntimeError("repeated controlled import registered duplicate routes")

        web_directory = getattr(module, "WEB_DIRECTORY", None)
        if web_directory is not None and not isinstance(web_directory, str):
            raise TypeError("WEB_DIRECTORY must be a string when present")
        result.update(
            {
                "status": "passed",
                "server_module": str(server_origin),
                "registration_style": style,
                "registration": registration,
                "web_directory": web_directory,
                "routes": first_routes,
                "repeat_import_idempotent": True,
                "captured_stdout": captured_stdout.getvalue(),
                "captured_stderr": captured_stderr.getvalue(),
            }
        )
        return result
    except Exception as exc:  # The CLI returns concise controlled-import evidence.
        return {**result, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if server_module is not None and hasattr(server_module, "PromptServer"):
            server_module.PromptServer.instance = original_instance
        sys.path[:] = saved_path
        sys.modules.pop("server", None)
        if saved_server is not None:
            sys.modules["server"] = saved_server
        sys.modules.pop("folder_paths", None)
        if saved_folder_paths is not None:
            sys.modules["folder_paths"] = saved_folder_paths
        for key in list(sys.modules):
            if key == module_name or key.startswith(module_name + "."):
                sys.modules.pop(key, None)
        sys.modules.update(saved_plugin_modules)


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
    result = check(args.plugin_root, args.comfy_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
