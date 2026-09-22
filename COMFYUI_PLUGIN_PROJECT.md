---
profile_schema: comfyui-plugin-project/v1
profile_status: complete
project_name: xiheha-toolkit
analyzed_at: 2026-09-19T14:41:11+08:00
declined_at: null
remind_after: null
analysis_scope: full-static
validation_level: simple
validation_model: "Gemini 3.8 Flash (High)"
validation_configured_at: 2026-09-22T19:43:36.888784+08:00
validation_agent: "Antigravity"
---

# xiheha-toolkit 项目档案

本文件记录稳定、可核对的项目事实，供后续开发首先读取。分析基于上述时间的当前工作树（包含未提交内容）；它不是源码替代品，也不记录瞬时 Git 状态。

## Purpose and boundaries

- ComfyUI 自定义节点工具库，节点分类根为 `xiheha-工具箱`，公共节点 ID 使用 `XH_` 前缀。
- 当前功能模块包括基础模型/LoRA 同目录 TXT 或 JSON sidecar 提示词配置（来源采集、配置选择、词条开关、提示词合并与展示）以及视频智能分割。
- 采用经典 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` 注册方式，前端由 `WEB_DIRECTORY = "./web"` 提供原生 ES Module 扩展。
- 这是可继续增加同级工具的通用库，不应把仓库边界限定为 sidecar 提示词工具。
- 当前版本源为根 `__init__.py` 的 `__version__ = "0.9.1"`。

## Authoritative files

| 路径 | 权威职责 | 修改时的同步点 |
| --- | --- | --- |
| `__init__.py` | 版本、Python 节点导入、公共 ID/显示名、`WEB_DIRECTORY`、路由注册 | 新节点/改名/发版必须核对这里 |
| `nodes/*.py` | ComfyUI 输入输出契约与执行行为 | 参数、返回槽、UI payload、测试、前端镜像 |
| `core/*.py` | 无 UI 的来源归一化、sidecar 解析/保存、提示词处理及共享视频 pipeline | 所有生产者/消费者及边界测试 |
| `server.py` / `routes/*.py` | 幂等路由入口；提示词配置与视频接口的独立处理器 | 前端 API client、输入校验、路径安全测试 |
| `web/shared/constants.js` | 前端节点 ID、外部 loader 映射、端口显示标签 | Python 注册/端口顺序/外部真实标识 |
| `web/xiheha_toolkit.js` | 唯一 `app.registerExtension` 入口和节点模块分发 | 新前端节点模块、外部 observer |
| `web/nodes/*.js` | 节点 ID、生命周期 patch 与 feature controller 安装入口 | Python 节点 ID、状态 widget、payload key |
| `web/features/*/` | 配置编辑器、提示词控制及视频分割器的状态、视图、接口/时间轴与 controller | 持久状态、异步序列、生命周期清理 |
| `web/shared/*.js` | graph、widgets、layout、workflow、payload、prompt-flow、API 与上游监听 | 外部端口/widget、异步刷新、状态键 |
| `web/shared/tooltip/` | Tooltip 纯解析与 DOM runtime；实例隔离和互斥唯一实现 | `web/styles/tooltip.css`、节点 controller |
| `web/toolkit.css` / `web/styles/*.css` | 主样式清单与各 feature 的单一 CSS 源 | 现有 `xh-*` class、加载顺序、按需 Tooltip |
| `tests/test_prompt_toolkit.py` | 解析、路径、节点契约和行为回归 | 任何用户可见行为或公共契约变更 |
| `tests/test_smart_video_splitter.py` / `tests/test_video_cutter.py` | 视频分割契约、算法、整数帧切片、缓存隔离与音频容错回归 | 视频分割功能变更 |
| `tests/test_shared_tooltip.py` / `tests/frontend/*.test.mjs` | Tooltip、编辑器状态、视频状态、样式单次加载与生命周期回归 | 前端纯模块或 runtime 边界变更 |
| `README.md` | 用户安装、节点和配置格式 | 只记录实际支持的用户行为 |
| `CHANGELOG.md` | 用户可见版本历史 | 用户可见变更和版本号同步 |
| `skills/comfyui-plugin-development/` | 通用 ComfyUI 插件开发、项目建档、最小入口生成和验证流程 | 修改技能后运行 skill 校验及对应脚本测试 |

## Node registry and contracts

所有节点当前均为普通单值输入/输出，没有声明 `INPUT_IS_LIST`、`OUTPUT_IS_LIST`、lazy 输入或异步执行。

### `XH_StackSource`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/easy_lora_stack.py::StackSource` / `easy-use兼容_模型列表获取` |
| 分类/函数 | `xiheha-工具箱/模型列表获取` / `get_source` |
| 必选输入 | `stack`: `LORA_STACK`，显示 `Lora堆` |
| 输出（顺序固定） | `LORA_STACK`/`Lora堆`；`XH_SOURCE`/`模型列表` |
| 行为 | 第一输出按对象身份透传；第二输出由 `stack_to_source` 生成，空栈为 `{"sources": []}` |
| 前端 | `web/nodes/stack-source.js`；应用端口标签、限制最小宽度 150px 并通知下游 selector |

### `XH_ModelSource`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/model_source.py::ModelSource` / `模型列表获取` |
| 分类/函数 | `xiheha-工具箱/模型列表获取` / `get_source` |
| 必选输入 | `model`: `MODEL`，显示 `模型` |
| 输出（顺序固定） | `MODEL`/`模型`；`XH_SOURCE`/`模型列表` |
| 行为 | MODEL 原对象透传；只从 `cached_patcher_init[1][0]` 读取 loader 源路径，无法识别时返回空来源，不重新加载模型 |
| 前端 | `web/nodes/model-source.js`；应用端口标签并通知下游 selector |

### `XH_PromptSelector`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/prompt_selector.py::PromptConfigSelector` / `选择提示词配置` |
| 分类/函数 | `xiheha-工具箱/提示词` / `select` |
| 必选输入（声明顺序） | `source`: `XH_SOURCE`，显示 `模型列表`；`selection_state`: `STRING`，默认 `{}`，显示 `配置选择状态` |
| 输出（顺序固定） | 三个 `STRING`：`模型名称`、`正向提示词`、`负向提示词` |
| 行为 | 每个来源读取 sidecar；未保存选择时默认首个配置；选择 `None`/关闭会跳过整行；三路以换行对齐 |
| 执行返回 | `{"ui": {"xh_rows": [<JSON 字符串>]}, "result": (names, positive, negative)}` |
| 持久状态 | `selection_state` 是工作流中的 JSON 字符串映射 `{source_name: config_index|null}`；前端将原 widget 隐藏而非删除 |
| 前端 | `web/nodes/prompt-selector.js`；`refreshSequence` 防止旧异步请求覆盖新请求，controller 为 `__xhSelector` |

### `XH_PromptPreview`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/prompt_preview.py::PromptPreview` / `模型提示词控制` |
| 分类/函数 | `xiheha-工具箱/提示词` / `preview` |
| 必选输入（声明顺序） | `model_names`、`positive_prompts`、`negative_prompts`: `STRING`、多行、`forceInput: true`；`token_state`: `STRING`、默认 `{}`、`hidden: true` |
| 输出（顺序固定） | 两个 `STRING`：`正向提示词`、`负向提示词` |
| 行为 | 逗号拆分词条；按开关过滤后分别合并，非空结果补尾部 ASCII 逗号；三路连接完整时前端才实时预览 |
| 执行返回 | `{"ui": {"xh_rows": [<JSON 字符串>]}, "result": (positive, negative)}`；行内 `context_id` 保持前后端配置上下文一致 |
| 持久状态 | `token_state` 用 `__xh_contexts` 记录当前各行的来源模型/配置上下文，词条键按该上下文、正负面和词条序号隔离，值缺省为启用；旧 `<model_name>|<side>|<index>` 键会迁移到当前配置 |
| 前端 | `web/nodes/prompt-preview.js`；纯状态位于 `web/features/prompt-preview/state.js`，隐藏状态 widget，controller 为 `__xhPreview` |

### `XH_PromptMerger`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/prompt_merge.py::PromptMerger` / `提示词合并` |
| 分类/函数 | `xiheha-工具箱/提示词` / `merge` |
| 必选输入 | `prompt_1`: `STRING`、多行、`forceInput: true`、显示 `提示词1` |
| 可选输入（顺序） | `prompt_2`、`prompt_3`、`prompt_4`: 同为 `STRING`、多行、`forceInput: true` |
| 输出 | `STRING`/`合并提示词` |
| 行为 | 各端口清洗并补尾逗号，忽略空值，按 1→4 用空格连接 |
| 执行返回 | `{"ui": {"xh_ports": [<固定四项 JSON 字符串>]}, "result": (merged,)}`；UI payload 保留空端口位置 |
| 前端 | `web/nodes/prompt-merger.js`；隐藏原输入 widget，controller 为 `__xhMerge` |

### `XH_PromptDisplay`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/prompt_display.py::PromptDisplay` / `显示提示词` |
| 分类/函数 | `xiheha-工具箱/提示词` / `display` |
| 必选输入（顺序） | `positive_prompts`、`negative_prompts`: `STRING`、多行、`forceInput: true` |
| 输出（顺序固定） | 两个 `STRING`：`正向提示词`、`负向提示词` |
| 行为 | `None` 变空字符串，其余转字符串，分别原样透传 |
| 执行返回 | `{"ui": {"xh_ports": [<两项 JSON 字符串>]}, "result": (positive, negative)}` |
| 前端 | `web/nodes/prompt-display.js`；隐藏原 widget，从 selector/preview 实时读取或用执行 payload 更新，controller 为 `__xhPromptDisplay` |

### `XH_PromptConfigEditor`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/prompt_config_editor.py::PromptConfigEditor` / `编辑提示词配置` |
| 分类/函数 | `xiheha-工具箱/提示词` / `edit`；`OUTPUT_NODE = True` |
| 必选输入（声明顺序） | `source`: `XH_SOURCE`，显示 `模型列表`；`editor_state`: `STRING`、默认 `{}`、`hidden: true` |
| 输出 | 无输出，`RETURN_TYPES = ()` |
| 行为 | 模型下拉选择；编辑既有配置或暂存一个“添加”配置；保存按钮以一次请求提交所有已加载模型的草稿；后端先生成全部写入计划，再按来源逐个提交，不提供跨文件回滚 |
| 持久状态 | `editor_state` 保存所选模型、各模型所选配置和未保存正负提示词草稿；不包含绝对路径 |
| 前端 | `web/nodes/prompt-config-editor.js` 安装 `web/features/prompt-config-editor/` controller；状态、DOM view 与异步保存分离，扫描使用 `refreshSequence` |

### `XH_SmartVideoSplitter`

| 项 | 值 |
| --- | --- |
| 实现/显示名 | `nodes/smart_video_splitter.py::SmartVideoSplitter` / `智能视频分割器` |
| 分类/函数 | `xiheha-工具箱/视频` / `process` |
| 必选输入（全部为 Widget，无连线端口） | `video`: 视频选择；`force_rate`: FLOAT，默认 0；`custom_width`: INT，默认 0；`custom_height`: INT，默认 540；`format`: 格式选择；`split_mode`: `target`/目标（默认）、`fuzzy`/模糊、`exact`/精确；`fuzzy_min`: 最短时长；`target_duration`: 目标时长（`fuzzy` 中保留但不参与计算）；`fuzzy_max`: 最长时长；`algorithm`: 检测模式，三档为智能自适应/快速内容/高运动抑制；`sensitivity`: 灵敏度；`cut_threshold`: 切镜阈值；`peak_prominence`: 突变显著度 |
| 隐藏输入 | `unique_id`: `UNIQUE_ID`；`splitter_state`: `STRING` |
| 输出（顺序固定） | `SMART_VIDEO_STREAM`/`视频流`；`AUDIO`/`音频`；`INT`/`帧数` |
| 行为 | `core/video_pipeline.py` 统一路径解析、参数规范化、尺寸、分段、切片和 manifest；目标/模糊模式组合颜色/亮度/边缘/感知哈希并检测硬切和渐变，智能与高运动模式按不同门槛使用光流抑制可解释运镜；`target` 按目标距离选点，`fuzzy` 在最低时长后采用最早可靠切点且无候选时按最长时长兜底，两者均使用一步前瞻；扫描窗口使用完整渐变上下文抑制边缘假候选；精确模式按帧固定间隔切分；FFmpeg 切片使用内部精确帧率和左闭右开的整数帧区间，视频与音频分别通过 `trim`/`atrim` 收尾，三位小数时间只供显示；节点执行只复用参数和内部修订标记均匹配的 manifest，前端主动计算强制重算 |
| 持久状态 | 原生 `video`、`split_mode`、`fuzzy_min`、`target_duration`、`fuzzy_max` widget 是工作流恢复基线；若宿主提供 `splitter_state` widget，则其 JSON 字段作为同步镜像优先覆盖对应值。工作流载入不会用创建默认值覆盖已恢复的原生 widget |
| 前端 | `web/nodes/smart-video-splitter.js` 安装 `web/features/smart-video-splitter/` controller；提供上传/计算、3.0~15.0s 时间轴、参数显隐及统一生命周期清理 |

## Custom data and persisted state

### `XH_SOURCE`

唯一规范结构：

```json
{
  "sources": [
    {
      "source_name": "subfolder/example.safetensors",
      "folder_name": "checkpoints"
    }
  ]
}
```

- `source_name` 必须是相对对应 ComfyUI 模型目录的路径；不允许绝对路径或 `..` 路径组件。
- `folder_name` 当前只允许 `loras`、`checkpoints`、`diffusion_models`。
- LoRA tuple/dict 在 `core/source_utils.py::stack_item_to_record` 归一化；强度字段不进入 `XH_SOURCE`。
- `StackSource` 和 `ModelSource` 是生产者，`PromptConfigSelector`、`PromptConfigEditor` 与本地接口是消费者。

### 解析结果

`core/config_parser.py::SourceInspection` 字段固定为：

- `source_name: str`
- `display_name: str`
- `config_file: str | None`（只返回文件名）
- `configs: list[PromptConfig]`
- `error: str | None`
- `folder_name: str`

`PromptConfig` 字段为 `index: int`、`positive: str`、`negative: str`、`labels: list[str]`。

### Sidecar 规则

查找顺序固定：

1. `模型名.txt`
2. `模型名.json`
3. `模型名.safetensors.json`
4. `模型名.safetensors.txt`

TXT 支持 `正向`、`负向`、`positive`、`negative` 及编号后缀，支持标签后续多行；没有标签的纯文本视为配置 1 的正向提示词。JSON 递归查找同类标签，并兼容顶层 `positive`/`prompt`/`positive_prompt` 与 `negative`/`negative_prompt`。

编辑器保存已有 sidecar 时沿用原文件路径和扩展名；没有 sidecar 时创建 `模型名.txt`。当前保存策略是**规范化重写**，不是无损局部更新：TXT 重写为 `正向/负向` 加编号标签，JSON 重写为同名键的顶层对象；未知字段、未识别文本、原键顺序、BOM、原换行风格和末尾空白不保证保留。涉及用户原文件时，不得把“原路径写回”描述成“内容无损”。

### `SMART_VIDEO_STREAM`

唯一规范结构：

```json
{
  "version": 1,
  "split_mode": "target",
  "source": {
    "path": "...",
    "filename": "example.mp4",
    "fps": 30.0,
    "effective_fps": 30.0,
    "width": 1920,
    "height": 1080,
    "duration": 42.37,
    "frame_count": 1271
  },
  "output": {
    "width": 960,
    "height": 540,
    "fps": 30.0,
    "model_format": "AnimatedDiff"
  },
  "settings": {
    "split_mode": "target",
    "min_duration": 4.0,
    "target_duration": 5.0,
    "max_duration": 6.0,
    "algorithm": "智能自适应检测（推荐）",
    "sensitivity": 0.60,
    "cut_threshold": 0.55,
    "peak_prominence": 0.12,
    "strong_cut_threshold": 0.75
  },
  "cache_dir": ".../temp/intelligent_video_splitter/node_xxx",
  "segments": [
    {
      "index": 0,
      "path": ".../segment_0001.mp4",
      "filename": "segment_0001.mp4",
      "start_time": 0.0,
      "end_time": 4.73,
      "duration": 4.73,
      "start_frame": 0,
      "end_frame": 142,
      "frame_count": 142,
      "cut_score": 0.87,
      "cut_type": "scene",
      "constraint_warning": false
    }
  ]
}
```

- 不包含图像 Tensor，仅传递轻量元数据与切片文件路径。
- 同步在节点专属缓存目录下写入 `manifest.json`。
- `start_frame`/`end_frame` 是实际裁切边界且采用左闭右开语义；`start_time`/`end_time`/`duration` 为三位小数展示值，不作为 FFmpeg 寻址输入。

## Frontend integration

- `web/xiheha_toolkit.js` 是唯一允许调用 `app.registerExtension` 的入口。
- 节点模块映射：`stack-source.js`、`model-source.js`、`prompt-selector.js`、`prompt-preview.js`、`prompt-merger.js`、`prompt-display.js`、`prompt-config-editor.js`、`smart-video-splitter.js`；后两个仅是 feature controller 的安装入口。
- 单向依赖目标：常量/纯状态/样式 → graph/widgets/layout/workflow/API 等共享模块 → feature controller → 节点入口 → 扩展入口。节点模块不直接互相导入。
- `web/shared/constants.js::PORT_LABELS` 是 Python 端口显示名的前端镜像；输出数组索引必须与 Python 槽位一致。
- selector/preview/merger/display 的 DOM 区域最小尺寸当前为 400×300；config editor 为 520×370，滚动 widget 最小内容高度 280；smart video splitter 节点最小尺寸为 350×700，上传视频、切换模式等自动布局只会补足或扩大尺寸，不会缩小用户手动设置的尺寸。
- `web/toolkit.css` 是唯一主样式清单，按顺序导入 `web/styles/base.css`、`prompt.css`、`config-editor.css`、`smart-video-splitter.css`；`tooltip.css` 只在启用定制卡片时按需加载，每个样式 ID 只安装一次。
- 工作流状态变更优先调用当前 ComfyUI 的 `activeWorkflow.changeTracker.captureCanvasState()`；旧图变更 API 仅作兼容回退，不合成鼠标事件。
- 选择器、提示词开关、配置编辑器和合并器的自定义 DOM controller 会在 `onConfigure` 写入原生 `widgets_values` 后重新水合；创建阶段默认值不得覆盖工作流已恢复的选择、开关、草稿或文本。
- 执行 UI payload key 只有 `xh_rows` 和 `xh_ports`；前端通过 `parseUiPayload` 读取数组第一个 JSON 值。

### 外部契约（不得重命名）

| 外部节点 | 标识/端口/widget | 用途 |
| --- | --- | --- |
| easy-use | 节点 ID `easy loraStack` | LoRA 来源追踪 |
| easy-use | 级联输入 `optional_lora_stack` | 向上合并堆 |
| easy-use | `toggle`、`mode`、`num_loras`、`lora_<n>_name` 及强度 widget | 变化监听；强度不写入 `XH_SOURCE` |
| ComfyUI loader | `CheckpointLoaderSimple` / `CheckpointLoader` / `unCLIPCheckpointLoader`, widget `ckpt_name` | `checkpoints` 来源 |
| ComfyUI loader | `UNETLoader`, widget `unet_name` | `diffusion_models` 来源 |

## Routes and trust boundaries

接口由 `register_routes()` 幂等注册，仅供当前 ComfyUI 前端使用：

- `POST /xiheha_toolkit/inspect`：只读扫描配置。
- `POST /xiheha_toolkit/save`：保存一个或多个来源的完整配置列表。
- `GET /xiheha_toolkit/video_info`：获取输入视频时长、分辨率、FPS 及帧数元数据。
- `GET /xiheha_toolkit/split_status`：查询节点当前切分或分析进度。
- `POST /xiheha_toolkit/split_video`：触发视频分析与多片段切割任务。

`server.py` 只负责幂等聚合注册；提示词接口实现在 `routes/prompt_config.py`，视频接口实现在 `routes/video.py`。

请求：

```json
{"sources": [{"source_name": "example.safetensors", "folder_name": "loras"}]}
```

响应：

```json
{"sources": [{"source_name": "example.safetensors", "display_name": "example", "config_file": null, "configs": [], "error": null, "folder_name": "loras"}]}
```

保存请求：

```json
{"sources": [{"source_name": "example.safetensors", "folder_name": "loras", "configs": [{"index": 1, "positive": "trigger", "negative": "lowres"}]}]}
```

保存响应仍为对应来源的 `SourceInspection` 数组，供编辑器用后端最终状态替换本地基线。

- 非 JSON、`sources` 非数组返回 400；一次最多 100 项。
- 路由只接纳 dict 项且字段为字符串，再由解析层限制目录并校验相对路径。
- `folder_paths.get_full_path` 负责注册目录解析；不把绝对路径返回前端。
- 单文件解析异常转换为简短 `error`，不泄漏堆栈；当前异常文本可能包含解析器消息，修改错误策略时需检查敏感信息。
- 前端调用仅在 `web/shared/api.js`，无互联网请求。
- 保存接口一次最多接收 100 个来源、每个来源 100 个配置、单项正向或负向提示词 100000 字符；路径由后端根据 `source_name`/`folder_name` 重新解析。
- 保存前确认模型真实路径仍位于 ComfyUI 登记目录；已有 sidecar 原路径原扩展名写回，无 sidecar 时创建 `模型名.txt`，写入采用同目录临时文件后原子替换。
- 批量保存会先验证全部请求并生成全部写入计划，再逐个文件提交。单文件替换具备原子性，但多个文件不构成事务：后续文件失败时，先前文件可能已更新且不会回滚；接口当前以整体 500 返回，响应不列出已成功项。前端在错误响应下保留本地草稿，但这不代表磁盘上没有部分成功。修改保存协议前必须明确部分失败、重试和草稿清理语义。
- 视频接口只接受 ComfyUI `input` 根下的相对文件名，拒绝绝对路径和 `..`；格式、算法、模式、数值范围和节点 ID 均在后端验证。
- `video_info` 不返回内部 `path`；切分状态不保存完整 stream；切分响应删除 source/segment 的 `path` 与 `cache_dir`。节点内部 `SMART_VIDEO_STREAM` 仍保留下游执行需要的真实路径。
- 视频接口的 500 响应使用固定错误文本，不回传原始异常、堆栈或文件系统路径。

## Model, latent, device, and memory behavior

- 本项目不执行推理算子，不处理 LATENT/IMAGE/CONDITIONING，不创建或缓存张量。
- `XH_ModelSource` 只读 `MODEL.cached_patcher_init` 的源路径元数据并按已登记根目录转换为相对路径。
- MODEL 与 LORA_STACK 的第一输出保持输入对象身份；无 clone、deepcopy、设备迁移、dtype 转换、patch 修改、显存清理或模型重新加载。
- 未携带 loader 元数据、路径不在 `checkpoints`/`diffusion_models` 根目录或无法解析时，模型仍透传，来源为空。

## Compatibility invariants

- 公共 ID、类型名、端口内部名、端口顺序和输出类型是工作流契约；除非用户明确接受破坏性变化，否则保持稳定。
- 当前已完成一次性 `LPT_` → `XH_`、`LORA_PROMPT_SOURCE` → `XH_SOURCE`、旧来源字段 → `sources/source_name` 迁移；当前代码不保留旧名兼容分支。
- 视频检测模式在 0.9.0 破坏性替换旧六算法枚举；旧值会明确报错，历史工作流需要重新选择三种新模式之一，输入内部名和顺序保持不变。
- 视频分段模式内部值为 `target`/目标、`fuzzy`/模糊、`exact`/精确，默认 `target`。按用户决定不兼容旧分段模式值：旧工作流原有 `fuzzy` 会表示新的模糊模式，需要手动重新选择“目标”。
- 不为外部 easy-use 标识创建本地别名，不修改其端口/widget 名。
- 前端预览和 Python 队列执行必须同时实现同一行为；不能只修一侧。
- `selection_state`、`token_state` 和 `editor_state` 属于保存工作流的状态，DOM controller 缓存不属于持久格式。
- `editor_state` 保存编辑器当前模型/配置选择和未保存草稿；保存成功后对应草稿会被清除。
- 编辑器保存期间禁用文本区和操作按钮，并以请求开始时构造的不可变 payload/草稿快照提交；旧响应不会清除请求开始后产生的新草稿，新增草稿会迁移到后端已分配的配置编号。
- 选择器异步请求必须保持序列保护，防止旧响应覆盖新来源。
- 视频 controller 的元数据请求和切分请求有序列保护；节点移除必须清理轮询器、文件输入、时间轴拖动监听器、Tooltip 注册及包装过的 widget callback。

## Validation map

### 自动测试

```powershell
$env:PYTHONPATH = "E:\HuiShi_launcher-WorkFisher-V2\ComfyUI"
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" -m unittest discover -s tests
```

Python 编译：

```powershell
$py = Get-ChildItem __init__.py,server.py,core\*.py,nodes\*.py | ForEach-Object { $_.FullName }
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" -m py_compile @py
```

前端语法：

```powershell
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" skills\comfyui-plugin-development\scripts\check_frontend_syntax.py --root .
```

前端纯模块与受控插件导入：

```powershell
node --test tests\frontend\*.test.mjs
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" skills\comfyui-plugin-development\scripts\check_plugin_import.py --root .
```

若固定路径不存在，使用可用 Python，并确保 ComfyUI 根目录进入 `PYTHONPATH`。注册/路由导入需要真实或受控的 ComfyUI 环境；不能把单独导入节点模块等同于插件完整导入。

### 手工 ComfyUI 验收

1. 在不影响现有工作流的独立 ComfyUI 实例中加载插件，八个节点能被搜索并显示正确分类、名称和端口。
2. Checkpoint/UNET loader → `模型列表获取` → 下游 MODEL 的透传不变；第二输出 → selector 能预览配置。
3. easy-use `easy loraStack`（含 `optional_lora_stack` 级联）→ stack adapter → selector 能按顺序获得 LoRA。
4. 快速修改上游 loader/LoRA 后 selector 只显示最新请求结果。
5. selector 三路连接 preview 后词条开关正确，不同配置的同位置词条开关彼此独立，保存并重开工作流后选择与开关状态不丢失。
6. merger 空端口占位和顺序正确；display 正负文本实时/执行后显示并保持两路透传。
7. config editor 可切换模型/配置，修改后星号位于按钮右上边框，跨模型草稿保留；保存后原配置文件更新，“添加”转为新编号并继续出现新“添加”。
8. 无 sidecar 时 editor 创建 `模型名.txt`；错误 sidecar、无模型源元数据时提示清晰且不无故阻断模型透传。
9. 视频节点可选择及上传根目录/子目录视频；目标/模糊/精确三种时间轴约束、主动计算、轮询进度、保存重开恢复、节点缩放和移除清理均正常。
10. 浏览器控制台无新增异常，DOM、样式和全局监听器不重复安装或越出节点。

## Documentation and release bookkeeping

- 用户可见行为变化：更新 `README.md`（如使用方式受影响）和 `CHANGELOG.md`。
- 版本号唯一代码源当前是根 `__init__.py::__version__`；发版变更与 changelog 版本同步。
- 工作流示例图片位于 `examples/images/workflow-example.png`；只有实际更新并核对示例时才声称其覆盖新行为。
- 新节点或结构变更同时更新本档案的注册表、端口、前端映射和验收路径。

## Unknowns and unverified items

- 本次档案创建完成了全仓库静态读取，但尚未因此启动 ComfyUI、打开浏览器或执行手工连线。
- 未因此验证当前 ComfyUI 版本的前端 API 兼容性、easy-use 实际安装版本或真实 loader widget 运行时形态。
- 未进行 GPU/显存测试；当前代码静态上不执行张量或推理操作。
- 档案创建时自动测试结果应以创建任务的交付报告为准，不在此处固化瞬时结果。

## Profile maintenance rules

以下变化必须在同一任务更新本文件：节点注册/显示名/分类、输入输出/状态、`XH_SOURCE` 或 sidecar 格式、前端模块/外部契约、接口/安全边界、模型行为、测试命令和手工验收路径。普通实现细节或瞬时 Git 状态不更新档案；局部更新不冒充全仓库重新解析，不随意刷新 `analyzed_at`。
