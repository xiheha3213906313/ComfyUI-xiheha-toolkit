"""Smart Video Splitter node implementation."""

from __future__ import annotations

from typing import Any

try:
    from ..core.video_meta import (
        DIMMAX,
        LOAD_FORMATS,
        get_input_video_files,
        get_lazy_audio,
    )
    from ..core.video_pipeline import VIDEO_ALGORITHMS, VideoSplitOptions, resolve_input_video, run_video_split
except (ImportError, ValueError):
    from core.video_meta import (
        DIMMAX,
        LOAD_FORMATS,
        get_input_video_files,
        get_lazy_audio,
    )
    from core.video_pipeline import VIDEO_ALGORITHMS, VideoSplitOptions, resolve_input_video, run_video_split

ALGORITHMS = list(VIDEO_ALGORITHMS)


class SmartVideoSplitter:
    """智能视频分割器：无输入端口，自动将视频切分为多个缓存片段并输出 SMART_VIDEO_STREAM。"""

    @classmethod
    def INPUT_TYPES(cls):
        files = get_input_video_files()
        return {
            "required": {
                "video": (files if files else ["none"], {
                    "tooltip": "【视频源文件】\n选择放置在 input 目录的待分割视频，或点击面板中的「上传视频」上传本地视频。"
                }),
                "force_rate": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 120.0, "step": 1.0,
                    "tooltip": "【强制帧率 (FPS)】\n强制将切片视频重采样为指定帧率。设为 0 时保持源视频原生帧率不变。"
                }),
                "custom_width": ("INT", {
                    "default": 0, "min": 0, "max": DIMMAX, "step": 8,
                    "tooltip": "【自定义宽度 (px)】\n输出片段的目标宽度。设为 0 时根据目标高度和原视频比例自动缩放并对齐倍数。"
                }),
                "custom_height": ("INT", {
                    "default": 540, "min": 0, "max": DIMMAX, "step": 8,
                    "tooltip": "【自定义高度 (px)】\n输出片段的目标高度（默认540）。若宽高均设为 0，则保持源视频原生分辨率。"
                }),
                "format": (list(LOAD_FORMATS.keys()), {
                    "default": "AnimatedDiff",
                    "tooltip": (
                        "【模型格式规范】\n"
                        "选择目标生成模型生态。系统将按目标模型规格自动计算倍数对齐（8x/16x/32x）与比例约束，对切片进行重采样与智能裁切。\n"
                        "• AnimatedDiff: 标准 8 像素对齐，兼顾通用 SD1.5 / SDXL\n"
                        "• Mochi: 16 像素降采样对齐，适配空间注意力机制\n"
                        "• LTX-Video: 32 像素重采样对齐，支持极高空间压缩比\n"
                        "• Wan (万相): Wan2.1 系列特化编码与补帧适配\n"
                        "• 原尺寸/自定义: 保持原始宽高比或严格按填写的自定义宽高输出"
                    ),
                }),
                "split_mode": (["fuzzy", "scene", "exact"], {
                    "default": "fuzzy",
                    "tooltip": (
                        "【分段模式】\n"
                        "• fuzzy (目标): 在最低～最高时长内选择最接近目标时长的可靠切镜点\n"
                        "• scene (模糊): 达到最低时长后遇到第一个可靠切镜点就切；没有切镜时在最高时长切分\n"
                        "• exact (精确): 按目标时长严格切分为等长区间，保留尾段余数"
                    )
                }),
                "fuzzy_min": ("FLOAT", {
                    "default": 4.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": "【场景分段最短时长 (秒)】\n目标和模糊模式允许切分的最小片段长度；数学上可满足时不会生成更短碎片。"
                }),
                "target_duration": ("FLOAT", {
                    "default": 5.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": (
                        "【目标分段时长 (秒)】\n"
                        "目标模式会在合法可靠切点中选择距离此时长最近的位置，"
                        "切镜强度只在距离相同时决定优先级；精确模式下为严格固定切片时长。"
                        "模糊模式不使用此参数。"
                    )
                }),
                "fuzzy_max": ("FLOAT", {
                    "default": 6.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": "【场景分段最长时长 (秒)】\n目标和模糊模式的片段上限；窗口内没有可靠切镜时会在此处兜底切分。"
                }),
                "algorithm": (ALGORITHMS, {
                    "default": "智能自适应检测（推荐）",
                    "tooltip": (
                        "【检测模式】\n"
                        "选择适合素材运动强度与处理速度的镜头检测策略：\n"
                        "• 智能自适应检测（推荐）: 适合剧情、混剪和一般短视频；识别硬切、淡入淡出与叠化，只在疑难候选附近使用光流校验\n"
                        "• 快速内容检测: 适合固定机位、访谈及长视频批处理；不计算光流，速度最快，快速运镜时可能产生误判\n"
                        "• 高运动抑制检测: 适合手持、运动、舞蹈及频繁推拉摇移；更积极使用运动补偿降低误切，分析耗时较高"
                    ),
                }),
                "sensitivity": ("FLOAT", {
                    "default": 0.60, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【检测灵敏度】\n"
                        "控制自适应背景阈值，默认值 0.60（范围 0.00 ~ 1.00）。\n"
                        "• 调高: 更容易保留短促硬切和较弱渐变，也可能增加误切\n"
                        "• 调低: 更保守，适合画面抖动或光线变化频繁的素材"
                    ),
                }),
                "cut_threshold": ("FLOAT", {
                    "default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【切镜阈值】\n"
                        "控制颜色、感知哈希、亮度和边缘组合证据的最低强度。默认值 0.55。\n"
                        "• 调高: 只接受更明确的场景变化，减少切片\n"
                        "• 调低: 保留较弱转场，但快速运动和特效更容易成为候选"
                    ),
                }),
                "peak_prominence": ("FLOAT", {
                    "default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【突变显著度】\n"
                        "要求硬切峰值高于前后背景变化，并控制渐变累计变化的有效强度。默认值 0.12。\n"
                        "• 调高: 更强地过滤抖动、闪光及连续运镜\n"
                        "• 调低: 更容易保留密集快切、较柔和的淡变与叠化"
                    ),
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "splitter_state": "STRING",
            },
        }

    RETURN_TYPES = ("SMART_VIDEO_STREAM", "AUDIO", "INT")
    RETURN_NAMES = ("视频流", "音频", "帧数")
    FUNCTION = "process"
    CATEGORY = "xiheha-工具箱/视频"

    @classmethod
    def VALIDATE_INPUTS(cls, video: str, algorithm: str | None = None, **kwargs: Any) -> bool | str:
        if not video or video == "none":
            return "请先选择或上传视频文件。"
        try:
            VideoSplitOptions.from_mapping({"algorithm": algorithm or ALGORITHMS[0]})
        except ValueError as exc:
            return str(exc)
        try:
            resolve_input_video(video)
        except (ValueError, FileNotFoundError) as exc:
            return str(exc) or "请先选择或上传视频文件。"
        return True

    def process(
        self,
        video: str,
        force_rate: float = 0.0,
        custom_width: int = 0,
        custom_height: int = 540,
        format: str = "AnimatedDiff",
        split_mode: str = "fuzzy",
        fuzzy_min: float = 4.0,
        target_duration: float = 5.0,
        fuzzy_max: float = 6.0,
        algorithm: str = "智能自适应检测（推荐）",
        sensitivity: float = 0.60,
        cut_threshold: float = 0.55,
        peak_prominence: float = 0.12,
        unique_id: str | int | None = None,
        splitter_state: str = "{}",
        **kwargs: Any,
    ) -> tuple[dict[str, Any], Any, int]:
        node_id = str(unique_id) if unique_id is not None else "default"
        _, video_path = resolve_input_video(video)
        options = VideoSplitOptions.from_mapping(
            {
                "force_rate": force_rate,
                "custom_width": custom_width,
                "custom_height": custom_height,
                "format": format,
                "split_mode": split_mode,
                "fuzzy_min": fuzzy_min,
                "target_duration": target_duration,
                "fuzzy_max": fuzzy_max,
                "algorithm": algorithm,
                "sensitivity": sensitivity,
                "cut_threshold": cut_threshold,
                "peak_prominence": peak_prominence,
            }
        )
        stream_data, meta = run_video_split(video_path, node_id, options, reuse_manifest=True)
        audio = get_lazy_audio(video_path, start_time=0.0, duration=meta["duration"])
        total_output_frames = sum(s["frame_count"] for s in stream_data.get("segments", []))
        return (stream_data, audio, total_output_frames)
