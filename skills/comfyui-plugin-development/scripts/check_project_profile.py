#!/usr/bin/env python3
"""Report the state of a ComfyUI plugin's canonical AI project profile."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


PROFILE_NAME = "COMFYUI_PLUGIN_PROJECT.md"
ALLOWED_STATUSES = {"complete", "partial", "declined"}
ALLOWED_VALIDATION_LEVELS = {"simple", "medium", "careful"}
FIELD_RE = re.compile(r"^([a-z_]+):\s*(.*?)\s*$")


def _unquote(value: str) -> str | None:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _frontmatter(path: Path) -> tuple[dict[str, str | None], str | None]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return {}, f"cannot read profile: {exc}"
    if not lines or lines[0].strip() != "---":
        return {}, "missing YAML frontmatter"
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}, "unterminated YAML frontmatter"
    fields: dict[str, str | None] = {}
    for line in lines[1:end]:
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = _unquote(match.group(2))
    return fields, None


def _parse_moment(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _validation_config(fields: dict[str, str | None], current_model: str | None) -> dict[str, object]:
    level = fields.get("validation_level")
    model = fields.get("validation_model")
    configured_at = _parse_moment(fields.get("validation_configured_at"))
    if level not in ALLOWED_VALIDATION_LEVELS or not model or not configured_at:
        return {"status": "missing"}

    normalized_current = str(current_model or "").strip()
    if not normalized_current:
        model_match: bool | None = None
    elif model.casefold() == "unknown":
        model_match = False
    else:
        model_match = model.casefold() == normalized_current.casefold()
    return {
        "status": "configured",
        "level": level,
        "model": model,
        "configured_at": configured_at.isoformat(),
        "current_model": normalized_current or None,
        "model_match": model_match,
        "model_confirmation_required": not bool(normalized_current),
    }


def inspect(root: Path, now: datetime, current_model: str | None = None) -> dict[str, object]:
    path = root.resolve() / PROFILE_NAME
    result: dict[str, object] = {"profile": str(path), "status": "missing"}
    if not path.is_file():
        return result

    fields, error = _frontmatter(path)
    if error:
        return {**result, "status": "invalid", "error": error}
    if fields.get("profile_schema") != "comfyui-plugin-project/v1":
        return {**result, "status": "invalid", "error": "unsupported or missing profile_schema"}

    profile_status = fields.get("profile_status")
    if profile_status not in ALLOWED_STATUSES:
        return {**result, "status": "invalid", "error": "invalid profile_status"}
    validation = _validation_config(fields, current_model)
    if profile_status in {"complete", "partial"}:
        if not _parse_moment(fields.get("analyzed_at")):
            return {**result, "status": "invalid", "error": "missing or invalid analyzed_at"}
        return {
            **result,
            "status": "ready",
            "profile_status": profile_status,
            "validation": validation,
        }

    declined_at = _parse_moment(fields.get("declined_at"))
    remind_after = _parse_moment(fields.get("remind_after"))
    if not declined_at or not remind_after:
        return {**result, "status": "invalid", "error": "declined profile needs declined_at and remind_after"}
    if now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    due = now >= remind_after
    return {
        **result,
        "status": "reminder_due" if due else "declined",
        "profile_status": profile_status,
        "remind_after": remind_after.isoformat(),
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="ComfyUI plugin root")
    parser.add_argument("--model", help="Exact current model label or identifier exposed by the host/runtime")
    parser.add_argument(
        "--now",
        type=_parse_moment,
        default=datetime.now().astimezone(),
        help="Override local time with a timezone-aware ISO-8601 timestamp",
    )
    args = parser.parse_args()
    if args.now is None:
        parser.error("--now must be a timezone-aware ISO-8601 timestamp")
    print(json.dumps(inspect(args.root, args.now, args.model), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
