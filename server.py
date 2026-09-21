"""Idempotent route registration entry point for xiheha-toolkit."""

from __future__ import annotations

from server import PromptServer

from .routes import register_prompt_config_routes, register_video_routes


_REGISTERED = False


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    routes = PromptServer.instance.routes
    register_prompt_config_routes(routes)
    register_video_routes(routes)
    _REGISTERED = True


__all__ = ["register_routes"]
