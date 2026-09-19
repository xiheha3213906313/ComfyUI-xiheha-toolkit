"""Source sidecar discovery and positive/negative config parsing."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import folder_paths

from .prompt_utils import clean_prompt_text, join_prompt_values
from .source_utils import MODEL_SOURCE_FOLDERS


SOURCE_FOLDERS = frozenset(("loras", *MODEL_SOURCE_FOLDERS))


_LABEL_RE = re.compile(r"^\s*(正向|负向|positive|negative)\s*(\d*)\s*$", re.IGNORECASE)
_LINE_RE = re.compile(r"^\s*(正向|负向|positive|negative)\s*(\d*)\s*[:：]\s*(.*)$", re.IGNORECASE)


@dataclass
class PromptConfig:
    """One numbered config, with positive and negative values kept separate."""

    index: int
    positive: str = ""
    negative: str = ""
    labels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceInspection:
    source_name: str
    display_name: str
    config_file: str | None
    configs: list[PromptConfig]
    error: str | None = None
    folder_name: str = "loras"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "display_name": self.display_name,
            "config_file": self.config_file,
            "configs": [config.to_dict() for config in self.configs],
            "error": self.error,
            "folder_name": self.folder_name,
        }


@dataclass(frozen=True)
class ConfigSavePlan:
    source_name: str
    folder_name: str
    target: Path
    configs: tuple[PromptConfig, ...]
    content: str


def _label_info(label: str) -> tuple[str, int] | None:
    match = _LABEL_RE.match(str(label))
    if not match:
        return None
    kind = match.group(1).casefold()
    kind = "positive" if kind in {"正向", "positive"} else "negative"
    index = int(match.group(2) or "1")
    return kind, max(index, 1)


def _candidate_sidecars(model_path: Path) -> list[Path]:
    # The order is deterministic and follows the requested naming variants.
    return [
        model_path.with_suffix(".txt"),
        model_path.with_suffix(".json"),
        Path(str(model_path) + ".json"),
        Path(str(model_path) + ".txt"),
    ]


def find_sidecar(model_path: str | Path) -> Path | None:
    for candidate in _candidate_sidecars(Path(model_path)):
        if candidate.is_file():
            return candidate
    return None


def _config_map(events: list[tuple[str, int, object, str]]) -> list[PromptConfig]:
    grouped: dict[int, PromptConfig] = {}
    for kind, index, value, label in events:
        config = grouped.setdefault(index, PromptConfig(index=index))
        if label not in config.labels:
            config.labels.append(label)
        current = getattr(config, kind)
        value_text = clean_prompt_text(value)
        if value_text:
            setattr(config, kind, join_prompt_values([current, value_text]))
    return [grouped[index] for index in sorted(grouped)]


def _parse_text(text: str) -> list[PromptConfig]:
    events: list[tuple[str, int, object, str]] = []
    current: tuple[str, int, str] | None = None
    for raw_line in text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = _LINE_RE.match(raw_line)
        if match:
            kind = "positive" if match.group(1).casefold() in {"正向", "positive"} else "negative"
            index = int(match.group(2) or "1")
            label = match.group(1) + (match.group(2) or "")
            events.append((kind, index, match.group(3), label))
            current = (kind, index, label)
        elif current and raw_line.strip():
            kind, index, label = current
            events.append((kind, index, raw_line.strip(), label))

    # A plain text sidecar is treated as positive config1.
    if not events:
        plain = clean_prompt_text(text)
        return [PromptConfig(index=1, positive=plain)] if plain else []
    return _config_map(events)


def _json_value_to_text(value: object) -> str:
    if isinstance(value, dict):
        return join_prompt_values(value.values())
    if isinstance(value, (list, tuple)):
        return join_prompt_values(value)
    return clean_prompt_text(value)


def _walk_json(value: object, events: list[tuple[str, int, object, str]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            label_info = _label_info(str(key))
            if label_info:
                kind, index = label_info
                events.append((kind, index, _json_value_to_text(item), str(key)))
            elif isinstance(item, (dict, list)):
                _walk_json(item, events)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                _walk_json(item, events)


def _parse_json(text: str) -> list[PromptConfig]:
    data = json.loads(text)
    events: list[tuple[str, int, object, str]] = []
    _walk_json(data, events)

    if not events and isinstance(data, dict):
        positive = data.get("positive", data.get("prompt", data.get("positive_prompt")))
        negative = data.get("negative", data.get("negative_prompt"))
        if positive is not None:
            events.append(("positive", 1, _json_value_to_text(positive), "positive"))
        if negative is not None:
            events.append(("negative", 1, _json_value_to_text(negative), "negative"))

    return _config_map(events)


def parse_sidecar(path: Path) -> list[PromptConfig]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.casefold() == ".json":
        return _parse_json(text)
    return _parse_text(text)


def _coerce_configs(configs: object) -> tuple[PromptConfig, ...]:
    if not isinstance(configs, (list, tuple)):
        raise ValueError("configs 必须是数组")

    normalized: list[PromptConfig] = []
    seen: set[int] = set()
    for item in configs:
        if isinstance(item, PromptConfig):
            index = item.index
            positive = item.positive
            negative = item.negative
        elif isinstance(item, dict):
            index = item.get("index")
            positive = item.get("positive", "")
            negative = item.get("negative", "")
        else:
            raise ValueError("配置项格式无效")
        if not isinstance(index, int) or isinstance(index, bool) or index < 1:
            raise ValueError("配置编号必须是正整数")
        if index in seen:
            raise ValueError("配置编号不能重复")
        if not isinstance(positive, str) or not isinstance(negative, str):
            raise ValueError("提示词必须是字符串")
        seen.add(index)
        normalized.append(
            PromptConfig(
                index=index,
                positive=clean_prompt_text(positive),
                negative=clean_prompt_text(negative),
            )
        )
    return tuple(sorted(normalized, key=lambda config: config.index))


def _serialize_text(configs: tuple[PromptConfig, ...]) -> str:
    lines: list[str] = []
    for config in configs:
        suffix = "" if config.index == 1 else str(config.index)
        lines.extend((f"正向{suffix}：{config.positive}", f"负向{suffix}：{config.negative}"))
    return "\n".join(lines) + ("\n" if lines else "")


def _serialize_json(configs: tuple[PromptConfig, ...]) -> str:
    payload: dict[str, str] = {}
    for config in configs:
        suffix = "" if config.index == 1 else str(config.index)
        payload[f"正向{suffix}"] = config.positive
        payload[f"负向{suffix}"] = config.negative
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def prepare_source_config_save(
    source_name: object,
    folder_name: object,
    configs: object,
) -> ConfigSavePlan:
    normalized = _safe_source_name(source_name)
    folder = str(folder_name or "loras")
    if not normalized:
        raise ValueError("模型名称无效")
    if folder not in SOURCE_FOLDERS:
        raise ValueError("不支持的模型目录")

    model_path_value = folder_paths.get_full_path(folder, normalized)
    if not model_path_value:
        raise ValueError("来源文件未找到")
    model_path = Path(model_path_value).resolve()
    roots = [Path(root).resolve() for root in folder_paths.get_folder_paths(folder)]
    if not any(model_path == root or root in model_path.parents for root in roots):
        raise ValueError("来源文件不在模型目录")
    if not model_path.is_file():
        raise ValueError("来源文件未找到")
    target = find_sidecar(model_path) or model_path.with_suffix(".txt")
    normalized_configs = _coerce_configs(configs)
    content = _serialize_json(normalized_configs) if target.suffix.casefold() == ".json" else _serialize_text(normalized_configs)
    return ConfigSavePlan(normalized, folder, target, normalized_configs, content)


def commit_source_config_save(plan: ConfigSavePlan) -> SourceInspection:
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=plan.target.parent,
            prefix=f".{plan.target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(plan.content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = handle.name
        os.replace(temporary_path, plan.target)
        temporary_path = None
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
    return inspect_source(plan.source_name, plan.folder_name)


def save_source_configs(source_name: object, folder_name: object, configs: object) -> SourceInspection:
    return commit_source_config_save(prepare_source_config_save(source_name, folder_name, configs))


def _display_name(source_name: str) -> str:
    return Path(source_name.replace("\\", "/")).stem


def _safe_source_name(value: object) -> str:
    normalized = str(value or "")
    if not normalized or normalized.startswith(("/", "\\")) or Path(normalized).is_absolute():
        return ""
    if ".." in normalized.replace("\\", "/").split("/"):
        return ""
    return normalized


def inspect_source(source_name: str, folder_name: str = "loras") -> SourceInspection:
    normalized = _safe_source_name(source_name)
    folder_name = str(folder_name or "loras")
    display_name = _display_name(normalized)
    if folder_name not in SOURCE_FOLDERS:
        return SourceInspection(normalized, display_name, None, [], "不支持的模型目录", folder_name)

    model_path = folder_paths.get_full_path(folder_name, normalized) if normalized else None
    if not model_path:
        return SourceInspection(normalized, display_name, None, [], "来源文件未找到", folder_name)

    sidecar = find_sidecar(model_path)
    if not sidecar:
        return SourceInspection(normalized, display_name, None, [], None, folder_name)

    try:
        configs = parse_sidecar(sidecar)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return SourceInspection(normalized, display_name, sidecar.name, [], f"配置文件解析失败: {exc}", folder_name)
    return SourceInspection(normalized, display_name, sidecar.name, configs, None, folder_name)


def inspect_sources(sources: list[object]) -> list[dict[str, Any]]:
    inspections: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = source.get("source_name", source.get("name", ""))
        folder_name = source.get("folder_name", "loras")
        if not isinstance(name, (str, int, float)):
            continue
        inspections.append(inspect_source(str(name), str(folder_name)).to_dict())
    return inspections
