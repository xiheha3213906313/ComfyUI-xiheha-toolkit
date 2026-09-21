from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_xiheha_toolkit_server_tests"


class _Routes:
    def __init__(self):
        self.handlers = {}

    def post(self, path):
        def decorator(handler):
            self.handlers[path] = handler
            return handler

        return decorator

    def get(self, path):
        def decorator(handler):
            self.handlers[path] = handler
            return handler

        return decorator


def _load_server_module():
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    sys.modules[PACKAGE_NAME] = package

    routes = _Routes()
    fake_server = types.ModuleType("server")
    fake_server.PromptServer = type("PromptServer", (), {"instance": type("Instance", (), {"routes": routes})()})
    previous_server = sys.modules.get("server")
    sys.modules["server"] = fake_server
    try:
        spec = importlib.util.spec_from_file_location(f"{PACKAGE_NAME}.server", ROOT / "server.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        if previous_server is None:
            sys.modules.pop("server", None)
        else:
            sys.modules["server"] = previous_server
    return module, routes


SERVER_MODULE, ROUTES = _load_server_module()
PROMPT_ROUTES = sys.modules[f"{PACKAGE_NAME}.routes.prompt_config"]
VIDEO_ROUTES = sys.modules[f"{PACKAGE_NAME}.routes.video"]
VIDEO_PIPELINE = sys.modules[f"{PACKAGE_NAME}.core.video_pipeline"]


class _Request:
    def __init__(self, payload=None, error=None, query=None):
        self.payload = payload
        self.error = error
        self.rel_url = type("RelUrl", (), {"query": query or {}})()

    async def json(self):
        if self.error:
            raise self.error
        return self.payload


class ServerValidationTests(unittest.TestCase):
    def test_valid_save_payload_is_normalized(self):
        sources = PROMPT_ROUTES.validate_save_sources(
            {
                "sources": [
                    {
                        "source_name": "folder/model.safetensors",
                        "folder_name": "checkpoints",
                        "configs": [{"index": 1, "positive": "good", "negative": "bad"}],
                    }
                ]
            }
        )
        self.assertEqual(sources[0]["configs"][0], {"index": 1, "positive": "good", "negative": "bad"})

    def test_save_payload_rejects_boolean_index(self):
        with self.assertRaisesRegex(ValueError, "正整数"):
            PROMPT_ROUTES.validate_save_sources(
                {
                    "sources": [
                        {
                            "source_name": "model.safetensors",
                            "folder_name": "loras",
                            "configs": [{"index": True, "positive": "", "negative": ""}],
                        }
                    ]
                }
            )

    def test_save_payload_rejects_oversized_prompt(self):
        with self.assertRaisesRegex(ValueError, "100000"):
            PROMPT_ROUTES.validate_save_sources(
                {
                    "sources": [
                        {
                            "source_name": "model.safetensors",
                            "folder_name": "loras",
                            "configs": [{"index": 1, "positive": "x" * 100_001, "negative": ""}],
                        }
                    ]
                }
            )

    def test_route_registration_is_idempotent(self):
        SERVER_MODULE.register_routes()
        SERVER_MODULE.register_routes()
        self.assertEqual(
            set(ROUTES.handlers),
            {
                "/xiheha_toolkit/inspect",
                "/xiheha_toolkit/save",
                "/xiheha_toolkit/video_info",
                "/xiheha_toolkit/split_status",
                "/xiheha_toolkit/split_video",
            },
        )

    def test_save_route_rejects_malformed_json(self):
        SERVER_MODULE.register_routes()
        response = asyncio.run(ROUTES.handlers["/xiheha_toolkit/save"](_Request(error=ValueError("bad"))))
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.text)["error"], "请求必须是 JSON")

    def test_save_route_returns_saved_inspections(self):
        SERVER_MODULE.register_routes()
        inspection = type("Inspection", (), {"to_dict": lambda self: {"source_name": "model.safetensors"}})()
        payload = {
            "sources": [
                {
                    "source_name": "model.safetensors",
                    "folder_name": "loras",
                    "configs": [{"index": 1, "positive": "good", "negative": "bad"}],
                }
            ]
        }
        with patch.object(PROMPT_ROUTES, "prepare_source_config_save", return_value=object()), patch.object(
            PROMPT_ROUTES, "commit_source_config_save", return_value=inspection
        ):
            response = asyncio.run(ROUTES.handlers["/xiheha_toolkit/save"](_Request(payload=payload)))
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text)["sources"], [{"source_name": "model.safetensors"}])

    def test_save_route_hides_filesystem_error_details(self):
        SERVER_MODULE.register_routes()
        payload = {
            "sources": [
                {
                    "source_name": "model.safetensors",
                    "folder_name": "loras",
                    "configs": [{"index": 1, "positive": "", "negative": ""}],
                }
            ]
        }
        with patch.object(PROMPT_ROUTES, "prepare_source_config_save", return_value=object()), patch.object(
            PROMPT_ROUTES, "commit_source_config_save", side_effect=OSError("C:/secret/path")
        ):
            response = asyncio.run(ROUTES.handlers["/xiheha_toolkit/save"](_Request(payload=payload)))
        self.assertEqual(response.status, 500)
        self.assertNotIn("secret", response.text)

    def test_video_info_removes_internal_path(self):
        SERVER_MODULE.register_routes()
        metadata = {
            "path": "C:/secret/input/video.mp4",
            "filename": "video.mp4",
            "duration": 3.0,
            "fps": 24.0,
            "width": 640,
            "height": 480,
            "frame_count": 72,
            "has_audio": True,
        }
        with patch.object(VIDEO_ROUTES, "resolve_input_video", return_value=("video.mp4", metadata["path"])), patch.object(
            VIDEO_ROUTES, "get_video_metadata", return_value=metadata
        ):
            response = asyncio.run(
                ROUTES.handlers["/xiheha_toolkit/video_info"](_Request(query={"filename": "video.mp4"}))
            )
        payload = json.loads(response.text)
        self.assertEqual(response.status, 200)
        self.assertNotIn("path", payload)
        self.assertNotIn("secret", response.text)

    def test_video_split_response_and_status_are_path_safe(self):
        SERVER_MODULE.register_routes()
        stream = {
            "version": 1,
            "split_mode": "exact",
            "cache_dir": "C:/secret/cache",
            "source": {"path": "C:/secret/input/video.mp4", "filename": "video.mp4"},
            "output": {"width": 640, "height": 480, "fps": 24.0, "model_format": "AnimatedDiff"},
            "settings": {"split_mode": "exact"},
            "segments": [{"path": "C:/secret/cache/segment.mp4", "duration": 3.0, "frame_count": 72}],
        }
        request = _Request(payload={"node_id": "12", "filename": "video.mp4", "split_mode": "exact"})
        with patch.object(VIDEO_ROUTES, "resolve_input_video", return_value=("video.mp4", "C:/secret/input/video.mp4")), patch.object(
            VIDEO_ROUTES, "run_video_split", return_value=(stream, {})
        ):
            response = asyncio.run(ROUTES.handlers["/xiheha_toolkit/split_video"](request))
        payload = json.loads(response.text)
        self.assertEqual(response.status, 200)
        self.assertNotIn("path", payload["stream"]["source"])
        self.assertNotIn("path", payload["stream"]["segments"][0])
        self.assertNotIn("cache_dir", payload["stream"])
        self.assertNotIn("secret", response.text)
        self.assertNotIn("stream", VIDEO_ROUTES.SPLIT_TASKS["12"])

    def test_video_request_boundaries(self):
        SERVER_MODULE.register_routes()
        absolute = asyncio.run(
            ROUTES.handlers["/xiheha_toolkit/video_info"](_Request(query={"filename": "C:/secret/video.mp4"}))
        )
        traversal = asyncio.run(
            ROUTES.handlers["/xiheha_toolkit/video_info"](_Request(query={"filename": "../video.mp4"}))
        )
        bad_node = asyncio.run(
            ROUTES.handlers["/xiheha_toolkit/split_status"](_Request(query={"node_id": "../bad"}))
        )
        self.assertEqual(absolute.status, 400)
        self.assertEqual(traversal.status, 400)
        self.assertEqual(bad_node.status, 400)
        with self.assertRaisesRegex(ValueError, "超出允许范围"):
            VIDEO_PIPELINE.VideoSplitOptions.from_mapping({"sensitivity": 2})
        with self.assertRaisesRegex(ValueError, "不受支持"):
            VIDEO_PIPELINE.VideoSplitOptions.from_mapping({"algorithm": "unknown"})
        with self.assertRaisesRegex(ValueError, "fuzzy 或 exact"):
            VIDEO_PIPELINE.VideoSplitOptions.from_mapping({"split_mode": ["exact"]})
        with self.assertRaisesRegex(ValueError, "必须是对象"):
            VIDEO_PIPELINE.VideoSplitOptions.from_mapping([])

    def test_video_500_does_not_echo_exception(self):
        SERVER_MODULE.register_routes()
        request = _Request(payload={"node_id": "14", "filename": "video.mp4"})
        with patch.object(VIDEO_ROUTES, "resolve_input_video", return_value=("video.mp4", "C:/secret/video.mp4")), patch.object(
            VIDEO_ROUTES, "run_video_split", side_effect=RuntimeError("C:/secret/ffmpeg failed")
        ):
            response = asyncio.run(ROUTES.handlers["/xiheha_toolkit/split_video"](request))
        self.assertEqual(response.status, 500)
        self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
