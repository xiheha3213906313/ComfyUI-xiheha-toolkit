#!/usr/bin/env python3
"""Persist a project's validation level and the model that selected it."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


PROFILE_NAME = "COMFYUI_PLUGIN_PROJECT.md"
LEVELS = ("simple", "medium", "careful")
FIELDS = ("validation_level", "validation_model", "validation_configured_at")


def _parse_moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def update(root: Path, level: str, model: str | None, configured_at: datetime) -> dict[str, object]:
    path = root.resolve() / PROFILE_NAME
    if not path.is_file():
        return {"status": "error", "profile": str(path), "error": "project profile not found"}

    try:
        original = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return {"status": "error", "profile": str(path), "error": str(exc)}

    lines = original.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {"status": "error", "profile": str(path), "error": "missing YAML frontmatter"}
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {"status": "error", "profile": str(path), "error": "unterminated YAML frontmatter"}

    existing_model = ""
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "validation_model":
            existing_model = value.strip().strip("\"'")
            break
    if existing_model.casefold() in {"", "null", "~"}:
        existing_model = ""
    model = str(model or "").strip() or existing_model
    if not model:
        return {
            "status": "error",
            "profile": str(path),
            "error": "--model is required when no validation_model is configured",
        }

    newline = "\r\n" if "\r\n" in original else "\n"
    values = {
        "validation_level": level,
        "validation_model": model,
        "validation_configured_at": configured_at.isoformat(),
    }
    seen: set[str] = set()
    for index in range(1, end):
        key = lines[index].partition(":")[0].strip()
        if key in values:
            lines[index] = f"{key}: {values[key]}{newline}"
            seen.add(key)
    missing = [f"{key}: {values[key]}{newline}" for key in FIELDS if key not in seen]
    lines[end:end] = missing
    updated = "".join(lines)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(updated)
            temp_name = handle.name
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        return {"status": "error", "profile": str(path), "error": str(exc)}
    return {
        "status": "updated",
        "profile": str(path),
        "validation_level": level,
        "validation_model": model,
        "validation_configured_at": configured_at.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="ComfyUI plugin root")
    parser.add_argument("--level", choices=LEVELS, required=True)
    parser.add_argument(
        "--model",
        help="Exact current host model label/identifier, or 'unknown'; omit to preserve the configured model",
    )
    parser.add_argument(
        "--configured-at",
        type=_parse_moment,
        default=datetime.now().astimezone(),
        help="Timezone-aware ISO-8601 timestamp",
    )
    args = parser.parse_args()
    result = update(args.root, args.level, args.model, args.configured_at)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
