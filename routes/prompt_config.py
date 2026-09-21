"""Prompt sidecar inspection and save routes."""

from __future__ import annotations

from aiohttp import web

from ..core.config_parser import commit_source_config_save, inspect_sources, prepare_source_config_save


MAX_SOURCES = 100
MAX_CONFIGS = 100
MAX_PROMPT_LENGTH = 100_000


def validate_save_sources(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("sources 必须是数组")
    if len(sources) > MAX_SOURCES:
        raise ValueError("一次最多保存 100 个来源")

    validated: list[dict[str, object]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("来源项格式无效")
        source_name = source.get("source_name")
        folder_name = source.get("folder_name", "loras")
        configs = source.get("configs")
        if not isinstance(source_name, str) or not isinstance(folder_name, str):
            raise ValueError("模型名称和目录必须是字符串")
        if not isinstance(configs, list):
            raise ValueError("configs 必须是数组")
        if len(configs) > MAX_CONFIGS:
            raise ValueError("每个模型最多保存 100 个配置")

        validated_configs: list[dict[str, object]] = []
        for config in configs:
            if not isinstance(config, dict):
                raise ValueError("配置项格式无效")
            index = config.get("index")
            positive = config.get("positive", "")
            negative = config.get("negative", "")
            if not isinstance(index, int) or isinstance(index, bool) or index < 1:
                raise ValueError("配置编号必须是正整数")
            if not isinstance(positive, str) or not isinstance(negative, str):
                raise ValueError("提示词必须是字符串")
            if len(positive) > MAX_PROMPT_LENGTH or len(negative) > MAX_PROMPT_LENGTH:
                raise ValueError("单项提示词不能超过 100000 个字符")
            validated_configs.append({"index": index, "positive": positive, "negative": negative})
        validated.append({"source_name": source_name, "folder_name": folder_name, "configs": validated_configs})
    return validated


async def inspect_prompt_sources(request):
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return web.json_response({"error": "请求必须是 JSON"}, status=400)

    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    if not isinstance(sources, list):
        return web.json_response({"error": "sources 必须是数组"}, status=400)
    if len(sources) > MAX_SOURCES:
        return web.json_response({"error": "一次最多扫描 100 个来源"}, status=400)

    safe_sources = [
        {
            "source_name": source.get("source_name", ""),
            "folder_name": source.get("folder_name", "loras"),
        }
        for source in sources
        if isinstance(source, dict)
        and isinstance(source.get("source_name", ""), str)
        and isinstance(source.get("folder_name", "loras"), str)
    ]
    return web.json_response({"sources": inspect_sources(safe_sources)})


async def save_prompt_sources(request):
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return web.json_response({"error": "请求必须是 JSON"}, status=400)

    try:
        sources = validate_save_sources(payload)
        plans = [
            prepare_source_config_save(source["source_name"], source["folder_name"], source["configs"])
            for source in sources
        ]
    except ValueError as exc:
        return web.json_response({"error": str(exc) or "配置保存请求无效"}, status=400)
    except (OSError, UnicodeError):
        return web.json_response({"error": "配置保存失败，请检查文件权限"}, status=500)

    try:
        inspections = [commit_source_config_save(plan).to_dict() for plan in plans]
    except (OSError, UnicodeError):
        return web.json_response({"error": "配置保存失败，请检查文件权限"}, status=500)
    return web.json_response({"sources": inspections})


def register_prompt_config_routes(routes) -> None:
    routes.post("/xiheha_toolkit/inspect")(inspect_prompt_sources)
    routes.post("/xiheha_toolkit/save")(save_prompt_sources)
