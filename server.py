"""Read-only HTTP endpoints used by the live frontend preview."""

from __future__ import annotations

from aiohttp import web
from server import PromptServer

from .core.config_parser import inspect_sources


_REGISTERED = False


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    prompt_server = PromptServer.instance

    @prompt_server.routes.post("/xiheha_toolkit/inspect")
    async def inspect(request):
        try:
            payload = await request.json()
        except (TypeError, ValueError):
            return web.json_response({"error": "请求必须是 JSON"}, status=400)

        sources = payload.get("sources", []) if isinstance(payload, dict) else []
        if not isinstance(sources, list):
            return web.json_response({"error": "sources 必须是数组"}, status=400)
        if len(sources) > 100:
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

    _REGISTERED = True
