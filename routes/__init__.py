"""Local HTTP route modules for xiheha-toolkit."""

from .prompt_config import register_prompt_config_routes
from .video import register_video_routes

__all__ = ["register_prompt_config_routes", "register_video_routes"]
