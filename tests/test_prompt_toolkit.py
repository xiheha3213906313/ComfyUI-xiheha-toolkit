from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config_parser import find_sidecar, inspect_source, parse_sidecar
from core.prompt_utils import ensure_trailing_comma, normalize_prompt_line
from core.source_utils import model_to_source
from nodes.easy_lora_stack import StackSource
from nodes.model_source import ModelSource
from nodes.prompt_preview import PromptPreview, build_preview_rows, preview_token_key
from nodes.prompt_selector import build_prompt_rows
from nodes.prompt_merge import PromptMerger


class PromptUtilityTests(unittest.TestCase):
    def test_chinese_commas_and_trailing_comma(self):
        self.assertEqual(normalize_prompt_line("anime face， realistic hair,,"), "anime face, realistic hair")
        self.assertEqual(ensure_trailing_comma("anime face， realistic hair"), "anime face, realistic hair,")


class SidecarTests(unittest.TestCase):
    def test_safetensors_sidecar_variant(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "sample.safetensors"
            model.write_bytes(b"")
            sidecar = Path(str(model) + ".txt")
            sidecar.write_text("正向：trigger", encoding="utf-8")
            self.assertEqual(find_sidecar(model), sidecar)

    def test_grouped_positive_and_negative_configs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.txt"
            path.write_text("正向：base\n负向：lowres\n正向2：style2\n负向2：bad anatomy", encoding="utf-8")
            configs = parse_sidecar(path)
        self.assertEqual([config.index for config in configs], [1, 2])
        self.assertEqual(configs[0].positive, "base")
        self.assertEqual(configs[0].negative, "lowres")
        self.assertEqual(configs[1].positive, "style2")
        self.assertEqual(configs[1].negative, "bad anatomy")

    def test_json_positive_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.json"
            path.write_text(json.dumps({"正向": "foo", "正向2": "bar", "负向2": ["bad", "ugly"]}), encoding="utf-8")
            configs = parse_sidecar(path)
        self.assertEqual(configs[0].positive, "foo")
        self.assertEqual(configs[1].positive, "bar")
        self.assertEqual(configs[1].negative, "bad, ugly")

    def test_model_sidecar_resolves_from_checkpoint_and_diffusion_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            for folder_name in ["checkpoints", "diffusion_models"]:
                model = Path(temp) / folder_name / "sample.safetensors"
                model.parent.mkdir(parents=True, exist_ok=True)
                model.write_bytes(b"")
                sidecar = model.with_suffix(".txt")
                sidecar.write_text("正向：trigger", encoding="utf-8")

                with patch("core.config_parser.folder_paths.get_full_path", return_value=str(model)):
                    inspection = inspect_source("sample.safetensors", folder_name)

                self.assertEqual(inspection.folder_name, folder_name)
                self.assertEqual(inspection.configs[0].positive, "trigger")

    def test_model_sidecar_name_variants(self):
        sidecar_paths = (
            lambda model: model.with_suffix(".txt"),
            lambda model: model.with_suffix(".json"),
            lambda model: Path(str(model) + ".json"),
            lambda model: Path(str(model) + ".txt"),
        )
        for make_sidecar in sidecar_paths:
            with self.subTest(make_sidecar=make_sidecar):
                with tempfile.TemporaryDirectory() as temp:
                    model = Path(temp) / "sample.safetensors"
                    model.write_bytes(b"")
                    sidecar = make_sidecar(model)
                    sidecar.write_text("正向：trigger", encoding="utf-8")
                    self.assertEqual(find_sidecar(model), sidecar)


class NodeBehaviorTests(unittest.TestCase):
    def test_model_source_node_passes_model_through_and_extracts_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = root / "checkpoints" / "subfolder" / "sample.safetensors"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"")
            model = type("Model", (), {})()
            model.cached_patcher_init = (object(), (str(model_path),))

            def get_folder_paths(folder_name):
                return [str(root / folder_name)]

            with patch("core.source_utils.folder_paths.get_folder_paths", side_effect=get_folder_paths):
                output_model, source = ModelSource().get_source(model)

            self.assertIs(output_model, model)
            self.assertEqual(
                source,
                {"sources": [{"source_name": "subfolder/sample.safetensors", "folder_name": "checkpoints"}]},
            )

    def test_model_source_node_extracts_diffusion_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = root / "diffusion_models" / "sample.safetensors"
            model_path.parent.mkdir(parents=True)
            model_path.write_bytes(b"")
            model = type("Model", (), {})()
            model.cached_patcher_init = (object(), (str(model_path),))

            with patch(
                "core.source_utils.folder_paths.get_folder_paths",
                side_effect=lambda folder_name: [str(root / folder_name)],
            ):
                source = model_to_source(model)

            self.assertEqual(source["sources"][0]["folder_name"], "diffusion_models")

    def test_model_source_node_without_loader_metadata_is_empty(self):
        model = object()
        output_model, source = ModelSource().get_source(model)
        self.assertIs(output_model, model)
        self.assertEqual(source, {"sources": []})

    def test_model_source_node_contract(self):
        inputs = ModelSource.INPUT_TYPES()
        self.assertEqual(list(inputs["required"]), ["model"])
        self.assertEqual(ModelSource.RETURN_TYPES, ("MODEL", "XH_SOURCE"))
        self.assertEqual(ModelSource.RETURN_NAMES, ("模型", "模型列表"))

    def test_stack_adapter_passes_through_upstream_stack(self):
        node = StackSource()
        self.assertEqual(list(node.INPUT_TYPES()["required"]), ["stack"])
        self.assertNotIn("optional", node.INPUT_TYPES())
        upstream = [("folder/sample.safetensors", 0.6, 0.4), ("other.safetensors", 0.75, 0.75)]
        stack, source = node.get_source(upstream)
        self.assertIs(stack, upstream)
        self.assertEqual([item["source_name"] for item in source["sources"]], ["folder/sample.safetensors", "other.safetensors"])

    def test_stack_adapter_preserves_strengths(self):
        node = StackSource()
        existing = [("base.safetensors", 1.0, 1.0)]
        stack, source = node.get_source(existing)
        self.assertEqual(stack, existing)
        self.assertEqual(source["sources"][0]["source_name"], "base.safetensors")

    def test_easy_stack_empty_matches_easy_use(self):
        stack, source = StackSource().get_source(None)
        self.assertIsNone(stack)
        self.assertEqual(source, {"sources": []})

    def test_preview_keeps_positive_and_negative_separate(self):
        rows = build_preview_rows("model-a\nmodel-b", "a，b\n", "bad, ugly\nwatermark")
        self.assertEqual(rows[0]["positive_tokens"], ["a", "b"])
        self.assertEqual(rows[0]["negative_tokens"], ["bad", "ugly"])
        self.assertEqual(rows[1]["positive_tokens"], [])

    def test_merge_adds_commas_in_port_order(self):
        result = PromptMerger().merge("one", "two,", "", "four，")
        self.assertEqual(result["result"], ("one, two, four,",))
        self.assertEqual(
            json.loads(result["ui"]["xh_ports"][0]),
            ["one,", "two,", "", "four,"],
        )

    def _make_inspection(self, source_name, display_name, configs):
        return type("Inspection", (), {
            "source_name": source_name,
            "display_name": display_name,
            "configs": configs,
        })()

    def _make_config(self, index, positive, negative=""):
        return type("Config", (), {"index": index, "positive": positive, "negative": negative})()

    def test_selector_skips_closed_rows(self):
        inspection = {
            "a.safetensors": self._make_inspection("a.safetensors", "a", [self._make_config(1, "a")]),
        }
        with patch("nodes.prompt_selector.inspect_source", side_effect=lambda name, folder="loras": inspection[name]):
            rows, _ = build_prompt_rows(
                {"sources": [{"source_name": "a.safetensors"}]},
                {"a.safetensors": None},
            )
        self.assertEqual(rows, [])

    def test_selector_keeps_multiple_sources_in_order(self):
        inspections = {
            "a.safetensors": self._make_inspection("a.safetensors", "模型A", [self._make_config(1, "a", "bad-a")]),
            "b.safetensors": self._make_inspection("b.safetensors", "模型B", [self._make_config(1, "b", "bad-b")]),
        }
        with patch("nodes.prompt_selector.inspect_source", side_effect=lambda name, folder="loras": inspections[name]):
            rows, _ = build_prompt_rows(
                {"sources": [{"source_name": "a.safetensors"}, {"source_name": "b.safetensors"}]},
                "{}",
            )
        self.assertEqual([row["display_name"] for row in rows], ["模型A", "模型B"])
        self.assertEqual([row["positive"] for row in rows], ["a,", "b,"])
        self.assertEqual([row["negative"] for row in rows], ["bad-a,", "bad-b,"])

    def test_selector_normalizes_existing_prompt_commas(self):
        inspection = {
            "a.safetensors": self._make_inspection("a.safetensors", "模型A", [self._make_config(1, "face, hair,", "lowres")]),
        }
        with patch("nodes.prompt_selector.inspect_source", side_effect=lambda name, folder="loras": inspection[name]):
            rows, _ = build_prompt_rows({"sources": [{"source_name": "a.safetensors"}]}, "{}")
        self.assertEqual(rows[0]["positive"], "face, hair,")
        self.assertEqual(rows[0]["negative"], "lowres,")

    def test_selector_accepts_model_source_folder(self):
        inspection = self._make_inspection("sample.safetensors", "模型A", [self._make_config(1, "a", "bad")])
        with patch("nodes.prompt_selector.inspect_source", return_value=inspection) as inspect:
            rows, _ = build_prompt_rows(
                {"sources": [{"source_name": "sample.safetensors", "folder_name": "checkpoints"}]},
                "{}",
            )
        inspect.assert_called_once_with("sample.safetensors", "checkpoints")
        self.assertEqual(rows[0]["display_name"], "模型A")

    def test_ports_have_chinese_display_names(self):
        self.assertEqual(StackSource.RETURN_NAMES, ("Lora堆", "模型列表"))
        self.assertEqual(PromptMerger.RETURN_NAMES, ("合并提示词",))

    def test_preview_requires_all_three_inputs(self):
        inputs = PromptPreview.INPUT_TYPES()
        self.assertEqual(
            list(inputs["required"])[:3],
            ["model_names", "positive_prompts", "negative_prompts"],
        )
        self.assertTrue(inputs["required"]["token_state"][1]["hidden"])
        for name in ["model_names", "positive_prompts", "negative_prompts"]:
            self.assertTrue(inputs["required"][name][1]["forceInput"])

    def test_preview_token_switch_filters_final_output(self):
        key = preview_token_key("模型A", "positive", 1)
        rows = build_preview_rows("模型A", "face, hair", "", {key: False})
        self.assertEqual(rows[0]["positive_enabled"], [True, False])
        result = PromptPreview().preview("模型A", "face, hair", "", {key: False})
        self.assertEqual(result["result"], ("face,", ""))

    def test_merge_has_one_required_and_three_optional_inputs(self):
        inputs = PromptMerger.INPUT_TYPES()
        self.assertEqual(list(inputs["required"]), ["prompt_1"])
        self.assertEqual(
            list(inputs["optional"]),
            ["prompt_2", "prompt_3", "prompt_4"],
        )
        for name in ["prompt_1", "prompt_2", "prompt_3", "prompt_4"]:
            section = "required" if name == "prompt_1" else "optional"
            self.assertTrue(inputs[section][name][1]["forceInput"])


if __name__ == "__main__":
    unittest.main()
