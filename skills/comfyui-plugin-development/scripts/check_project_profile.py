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
QUESTION_TOOLS = {
    "codex": ("Codex", "request_user_input"),
    "claudecode": ("Claude Code", "AskUserQuestion"),
    "antigravity": ("Antigravity", "ask_question"),
    "cursor": ("Cursor", "AskQuestion"),
    "githubcopilot": ("GitHub Copilot", "ask_user"),
    "opencode": ("OpenCode", "question"),
    "workbuddy": ("workbuddy", "AskUserQuestion"),
}


def _unquote(value: str) -> str | None:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else value
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
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


def _normalize_agent(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _question_tool(fields: dict[str, str | None], current_agent: str | None) -> dict[str, object]:
    configured_agent = str(fields.get("validation_agent") or "").strip() or None
    normalized_current = str(current_agent or "").strip() or None
    candidate_agent = normalized_current or configured_agent
    mapped = QUESTION_TOOLS.get(_normalize_agent(candidate_agent))
    return {
        "configured_agent": configured_agent,
        "current_agent": normalized_current,
        "candidate_source": (
            "current_agent"
            if normalized_current
            else "configured_agent_hint"
            if configured_agent
            else "none"
        ),
        "canonical_agent": mapped[0] if mapped else None,
        "preferred_tool": mapped[1] if mapped else None,
        "match": "known_agent" if mapped else "unmatched",
        "availability_must_be_checked": True,
        "fallback_action": "search_available_tools_for_user_input",
    }


def _validation_config(fields: dict[str, str | None], current_model: str | None) -> dict[str, object]:
    level = fields.get("validation_level")
    model = fields.get("validation_model")
    configured_at = _parse_moment(fields.get("validation_configured_at"))
    if level not in ALLOWED_VALIDATION_LEVELS or not model or not configured_at:
        return {
            "status": "missing",
            "action": "choose_validation_strategy",
            "blocking": True,
            "reason": "validation_configuration_missing",
        }

    normalized_current = str(current_model or "").strip()
    if not normalized_current or normalized_current.casefold() == "unknown":
        model_match: bool | None = None
        action = "confirm_validation_strategy"
        blocking = True
        reason = "current_model_unavailable"
    elif model.casefold() == "unknown":
        model_match = False
        action = "confirm_validation_strategy"
        blocking = True
        reason = "configured_model_unknown"
    else:
        model_match = model.casefold() == normalized_current.casefold()
        action = "continue" if model_match else "confirm_validation_strategy"
        blocking = not model_match
        reason = "model_match" if model_match else "model_mismatch"
    return {
        "status": "configured",
        "level": level,
        "model": model,
        "configured_at": configured_at.isoformat(),
        "current_model": normalized_current or None,
        "model_match": model_match,
        "model_confirmation_required": not bool(normalized_current)
        or normalized_current.casefold() == "unknown",
        "action": action,
        "blocking": blocking,
        "reason": reason,
    }


def inspect(
    root: Path,
    now: datetime,
    current_model: str | None = None,
    current_agent: str | None = None,
) -> dict[str, object]:
    path = root.resolve() / PROFILE_NAME
    result: dict[str, object] = {
        "profile": str(path),
        "status": "missing",
        "question_tool": _question_tool({}, current_agent),
    }
    if not path.is_file():
        return result

    fields, error = _frontmatter(path)
    if error:
        return {**result, "status": "invalid", "error": error}
    result["question_tool"] = _question_tool(fields, current_agent)
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
            "status": "ready" if profile_status == "complete" else "partial",
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
    parser.add_argument("--agent", help="Current coding-agent host name, such as Codex or Claude Code")
    parser.add_argument(
        "--now",
        type=_parse_moment,
        default=datetime.now().astimezone(),
        help="Override local time with a timezone-aware ISO-8601 timestamp",
    )
    args = parser.parse_args()
    if args.now is None:
        parser.error("--now must be a timezone-aware ISO-8601 timestamp")
    print(json.dumps(inspect(args.root, args.now, args.model, args.agent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
