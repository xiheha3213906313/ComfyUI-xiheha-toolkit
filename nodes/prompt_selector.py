"""Source sidecar configuration selector node."""

from __future__ import annotations

import json
from typing import Any

try:
    from ..core.config_parser import inspect_source
    from ..core.prompt_utils import clean_prompt_text, ensure_trailing_comma
    from ..core.source_utils import basename_without_extension, stack_item_to_record
except ImportError:  # Allows the test suite to import this module standalone.
    from core.config_parser import inspect_source
    from core.prompt_utils import clean_prompt_text, ensure_trailing_comma
    from core.source_utils import basename_without_extension, stack_item_to_record


def _source_records(source: object) -> list[dict[str, Any]]:
    if isinstance(source, dict):
        source = source.get("sources", [])
    if not isinstance(source, (list, tuple)):
        return []

    records: list[dict[str, Any]] = []
    for item in source:
        record = stack_item_to_record(item)
        if record:
            records.append(record)
    return records


def _read_selection_state(value: object) -> dict[str, int | None]:
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    if not isinstance(raw, dict):
        return {}

    result: dict[str, int | None] = {}
    for key, selection in raw.items():
        if selection in (None, "", "off", "关闭"):
            result[str(key)] = None
            continue
        try:
            result[str(key)] = int(selection)
        except (TypeError, ValueError):
            result[str(key)] = None
    return result


def build_prompt_rows(source: object, selection_state: object = "{}") -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    state = _read_selection_state(selection_state)
    rows: list[dict[str, Any]] = []

    for record in _source_records(source):
        source_name = record["source_name"]
        folder_name = record.get("folder_name", "loras")
        inspection = inspect_source(source_name, folder_name)
        config_map = {config.index: config for config in inspection.configs}
        available = sorted(config_map)

        if source_name not in state:
            state[source_name] = available[0] if available else None
        elif state[source_name] not in config_map and state[source_name] is not None:
            state[source_name] = available[0] if available else None

        selected = state[source_name]
        # "关闭" means the entire row is omitted, as requested.
        if selected is None or selected not in config_map:
            continue

        config = config_map[selected]
        rows.append(
            {
                "source_name": source_name,
                "display_name": inspection.display_name or basename_without_extension(source_name),
                "config_index": selected,
                "positive": ensure_trailing_comma(config.positive),
                "negative": ensure_trailing_comma(config.negative),
            }
        )

    return rows, state


class PromptConfigSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": ("XH_SOURCE", {"display_name": "模型列表"}),
                # The frontend replaces this widget with the radio-button UI,
                # while the string remains part of the normal workflow data.
                "selection_state": ("STRING", {"default": "{}", "multiline": False, "display_name": "配置选择状态"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("模型名称", "正向提示词", "负向提示词")
    FUNCTION = "select"
    CATEGORY = "xiheha-工具箱/提示词"

    def select(self, source, selection_state="{}"):  # noqa: ARG002
        rows, _ = build_prompt_rows(source, selection_state)
        model_names = "\n".join(row["display_name"] for row in rows)
        positive_prompts = "\n".join(row["positive"] for row in rows)
        negative_prompts = "\n".join(row["negative"] for row in rows)
        rows_json = json.dumps(rows, ensure_ascii=False)
        return {
            "ui": {"xh_rows": [rows_json]},
            "result": (model_names, positive_prompts, negative_prompts),
        }
