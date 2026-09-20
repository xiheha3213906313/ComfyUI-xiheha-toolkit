#!/usr/bin/env python3
"""Persist a project's validation level, model binding, and coding-agent host."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


PROFILE_NAME = "COMFYUI_PLUGIN_PROJECT.md"
LEVELS = ("simple", "medium", "careful")
FIELDS = ("validation_level", "validation_model", "validation_agent", "validation_configured_at")


def _decode_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else value
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _parse_moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def update(
    root: Path,
    level: str,
    model: str | None,
    configured_at: datetime,
    agent: str | None = None,
) -> dict[str, object]:
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
    existing_agent = ""
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "validation_model":
            existing_model = _decode_scalar(value)
        elif separator and key.strip() == "validation_agent":
            existing_agent = _decode_scalar(value)
    if existing_model.casefold() in {"", "null", "~"}:
        existing_model = ""
    model = str(model or "").strip() or existing_model
    if not model:
        return {
            "status": "error",
            "profile": str(path),
            "error": "--model is required when no validation_model is configured",
        }
    if existing_agent.casefold() in {"", "null", "~"}:
        existing_agent = ""
    agent = str(agent or "").strip() or existing_agent or "unknown"

    newline = "\r\n" if "\r\n" in original else "\n"
    values = {
        "validation_level": level,
        "validation_model": json.dumps(model, ensure_ascii=False),
        "validation_agent": json.dumps(agent, ensure_ascii=False),
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
        "validation_agent": agent,
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
        "--agent",
        help="Current coding-agent host name; omit to preserve it or record 'unknown' when absent",
    )
    parser.add_argument(
        "--configured-at",
        type=_parse_moment,
        default=datetime.now().astimezone(),
        help="Timezone-aware ISO-8601 timestamp",
    )
    args = parser.parse_args()
    result = update(args.root, args.level, args.model, args.configured_at, args.agent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
