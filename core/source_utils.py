"""Normalize source metadata from ComfyUI models and external stacks."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import folder_paths


MODEL_SOURCE_FOLDERS = ("checkpoints", "diffusion_models")


def stack_item_to_record(item: object) -> dict[str, Any] | None:
    folder_name = None
    if isinstance(item, dict):
        name = item.get("source_name", item.get("name", ""))
        model_strength = item.get("model_strength", item.get("strength", 1.0))
        clip_strength = item.get("clip_strength", item.get("strength", 1.0))
        folder_name = item.get("folder_name")
    elif isinstance(item, (list, tuple)) and item:
        name = item[0]
        model_strength = item[1] if len(item) > 1 else 1.0
        clip_strength = item[2] if len(item) > 2 else model_strength
    else:
        return None

    if not name or str(name) == "None":
        return None
    record = {
        "source_name": str(name),
        "model_strength": float(model_strength),
        "clip_strength": float(clip_strength),
    }
    if folder_name is not None:
        record["folder_name"] = str(folder_name or "loras")
    return record


def stack_to_source(stack: Iterable[object] | None) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for item in stack or []:
        record = stack_item_to_record(item)
        if record:
            records.append(record)
    return {"sources": records}


def _model_source_path(model: object) -> str | None:
    cached_init = getattr(model, "cached_patcher_init", None)
    if not isinstance(cached_init, (tuple, list)) or len(cached_init) < 2:
        return None

    arguments = cached_init[1]
    if not isinstance(arguments, (tuple, list)) or not arguments:
        return None

    path = arguments[0]
    if not isinstance(path, (str, os.PathLike)):
        return None
    return os.fspath(path)


def _relative_model_source(path: str) -> tuple[str, str] | None:
    absolute_path = os.path.abspath(path)
    matches: list[tuple[int, str, str]] = []

    for folder_name in MODEL_SOURCE_FOLDERS:
        for root in folder_paths.get_folder_paths(folder_name):
            absolute_root = os.path.abspath(root)
            try:
                if os.path.normcase(os.path.commonpath((absolute_path, absolute_root))) != os.path.normcase(absolute_root):
                    continue
            except ValueError:
                continue

            relative = os.path.relpath(absolute_path, absolute_root)
            if relative == os.pardir or relative.startswith(os.pardir + os.sep):
                continue
            matches.append((len(absolute_root), folder_name, relative))

    if not matches:
        return None
    _, folder_name, relative = max(matches)
    return folder_name, Path(relative).as_posix()


def model_to_source(model: object) -> dict[str, Any]:
    """Expose the source file of a core ComfyUI MODEL as prompt metadata."""

    path = _model_source_path(model)
    if not path:
        return {"sources": []}

    source = _relative_model_source(path)
    if source is None:
        return {"sources": []}

    folder_name, relative = source
    return {"sources": [{"source_name": relative, "folder_name": folder_name}]}


def basename_without_extension(name: str) -> str:
    return os.path.splitext(os.path.basename(str(name).replace("\\", "/")))[0]
