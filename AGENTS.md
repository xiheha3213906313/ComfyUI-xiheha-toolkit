# xiheha-toolkit AI 开发文档

本文档是本插件目录的开发入口。任何 AI 或开发者在修改本插件前，都必须先阅读本文档，再阅读与任务相关的源码。目标是让改动小、可回滚、可验证。

本文档只约束本插件目录内的开发行为；如果系统、用户、上级目录的 `AGENTS.md` 或 ComfyUI 官方接口有更高优先级要求，应同时遵守更高优先级规则。

## 1. 项目定位与真实结构

本项目是一个通用的 ComfyUI 自定义节点**工具库**（节点分类根目录 `xiheha-工具箱`，节点 ID 统一使用 `XH_` 前缀），会持续沉淀多类独立的小工具。当前已落地的功能模块是**模型来源提示词配置**：读取模型/LoRA 旁边的 TXT 或 JSON sidecar 配置，并通过可视化节点完成来源采集、配置选择、提示词预览开关与多路合并。后续新增工具属于同级模块，不要把整个库描述成只服务于 sidecar 提示词。

目录职责如下：

| 路径 | 职责 | 修改原则 |
| --- | --- | --- |
| `__init__.py` | 节点导入、节点 ID 注册、显示名称、版本号 | 新节点必须在这里注册 |
| `nodes/` | ComfyUI 节点输入输出与执行逻辑 | 只放节点行为，不把前端或 HTTP 逻辑塞进来 |
| `core/` | sidecar 解析、提示词清洗、来源数据转换等通用能力 | 保持通用、无 UI、无网络请求；可被不同工具模块复用 |
| `server.py` | 本地只读预览接口 | 只服务本插件前端；必须校验输入 |
| `web/` | LiteGraph/ComfyUI 前端增强、动态预览 | 前端节点 ID、端口名必须和 Python 对齐 |
| `tests/` | 解析器和节点行为测试 | 新行为必须增加回归测试 |
| `README_ZH_CN.md` | 用户安装、连接和配置说明 | 只写用户真正需要知道的行为 |
| `CHANGELOG.md` | 版本变更记录 | 每个用户可见功能变更都记录 |

### 1.1 命名标准（当前版本已统一，不保留旧版兼容）

- 节点 ID：统一 `XH_` 前缀（如 `XH_ModelSource`），不再使用历史的 `LPT_` 前缀。
- 自定义数据类型：统一 `XH_` 前缀（当前为 `XH_SOURCE`），不再使用 `LORA_PROMPT_SOURCE`。
- 来源数据字段：统一 `sources` / `source_name`，不再使用 `loras` / `lora_name`。
- 前端内部属性、DOM class、UI payload key 统一 `xh` / `XH` 前缀（如 `__xhSelector`、`.xh-row`、`xh_rows`）。
- 本版本是一次性重命名，**不需要兼容旧 ID、旧字段、旧工作流**；代码中不要再写旧名到新名的兼容分支。

### 1.2 当前节点注册表

| 节点 ID | 类名（`nodes/`） | 显示名称 | 输入 | 输出 |
| --- | --- | --- | --- | --- |
| `XH_StackSource` | `StackSource`（`easy_lora_stack.py`） | `easy-use兼容_模型列表获取` | `stack`: `LORA_STACK`（必选） | `LORA_STACK`（Lora堆）、`XH_SOURCE`（模型列表） |
| `XH_ModelSource` | `ModelSource`（`model_source.py`） | `模型列表获取` | `model`: `MODEL`（必选） | `MODEL`（模型）、`XH_SOURCE`（模型列表） |
| `XH_PromptSelector` | `PromptConfigSelector`（`prompt_selector.py`） | `选择提示词配置` | `source`: `XH_SOURCE`、`selection_state`: `STRING` | 模型名称、正向提示词、负向提示词 |
| `XH_PromptPreview` | `PromptPreview`（`prompt_preview.py`） | `模型提示词控制` | `model_names`/`positive_prompts`/`negative_prompts` 三路 STRING、隐藏 `token_state` | 正向提示词、负向提示词 |
| `XH_PromptMerger` | `PromptMerger`（`prompt_merge.py`） | `提示词合并` | `prompt_1` 必选，`prompt_2`~`prompt_4` 可选 | 合并提示词 |

## 2. 开发前的标准流程

开始修改前，按以下顺序执行，不要直接凭猜测改文件：

1. 明确用户要改变的行为、输入、输出。若需求涉及模型、路径、节点类型或前端交互，先在仓库中搜索真实实现。
2. 阅读本文件、根入口、目标节点、相关 core 工具、相关前端代码和现有测试。
3. 检查工作区状态，识别已有修改和未跟踪文件。已有修改属于用户，不能覆盖、重置或顺手清理。
4. 用搜索工具检索节点 ID、函数名、端口名、类型名和 API 路由的所有引用，确认改动范围。
5. 先确定最小责任层：节点行为放 `nodes/`，通用解析放 `core/`，预览交互放 `web/`，路径校验和扫描入口放 `server.py` 或解析器边界。
6. 形成简短实现方案，列出要改的文件、测试场景和不做的事情。
7. 使用最小补丁实现；实现过程中不要顺便重命名、重排目录、升级依赖或重写无关代码。
8. 先运行针对性测试，再运行完整测试、静态检查和必要的 ComfyUI 手工验证。
9. 最后检查工作区差异、文档和版本记录，向用户报告改了什么、测试结果和剩余限制。

如果需求无法从源码判断，才向用户询问。不要用问题代替本来可以通过搜索、调用方和测试确认的事实。

## 3. 编写 ComfyUI 节点

### 3.1 标准节点契约

每个节点都应遵守 ComfyUI 的基本约定：

```python
class ExampleNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"display_name": "模型"}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("模型",)
    FUNCTION = "run"
    CATEGORY = "xiheha-工具箱/分类"

    def run(self, model):
        return (model,)
```

必须注意：

- `INPUT_TYPES` 中的键名必须和执行函数参数名一致。
- `RETURN_TYPES`、`RETURN_NAMES`、实际返回值数量和顺序必须一致。
- 普通节点返回 tuple；需要向前端传执行结果时，使用当前项目已有的 `{"ui": ..., "result": (...)}` 结构。
- 输入和输出只声明节点实际读取或拥有的数据。不要添加占位输入、无用的透传输入或“为了连线方便”的额外输出。
- 可选输入只有在没有连接时也能正常执行，或确实存在有效的无输入路径时才使用 `optional`。
- 需要用户连接上游对象时使用正确的 ComfyUI 类型，例如 `MODEL`、`CLIP`、`VAE`、`LORA_STACK`、`XH_SOURCE`、`STRING`。
- 中文端口名通过 `RETURN_NAMES` 和 `display_name` 提供；如果前端还会动态改名，必须同步更新 `web/shared/constants.js` 的 `PORT_LABELS`。
- 新节点使用新的稳定 `XH_` ID。不要更改既有节点 ID、端口顺序或输出类型。

### 3.2 节点注册

新增节点至少需要：

1. 在独立的 `nodes/*.py` 文件中实现类。
2. 在根目录 `__init__.py` 导入类。
3. 在 `NODE_CLASS_MAPPINGS` 中加入稳定的 `XH_` 节点 ID。
4. 在 `NODE_DISPLAY_NAME_MAPPINGS` 中加入用户看到的名称。
5. 如果节点有动态端口、DOM UI 或端口标签：在 `web/shared/constants.js` 加入节点 ID 常量和 `PORT_LABELS`，新建 `web/nodes/<节点名>.js`（导出 `NODE_ID` 和 `patch(nodeType)`，内聚该节点的 controller 与生命周期钩子），并在 `web/xiheha_toolkit.js` 的 `NODE_MODULES` 中登记。前端为原生 ES Module，模块互引必须带 `.js` 后缀，且只有入口文件可以调用 `app.registerExtension`。
6. 增加节点契约和行为测试。

### 3.3 模型、设备和显存

- 节点不得重新加载已经输入的模型。
- 透传模型时直接返回原对象；不要 clone、deepcopy、移动设备或修改 patch。
- 不在模型节点中添加 `torch.no_grad`、`torch.inference_mode`、显式冻结/解冻或训练开关。
- 不在模型代码中做显存清理、卸载、设备转移或持久化大张量缓存。
- 保持输入 dtype、device、latent layout 和 ComfyUI 的 offload 行为；不要为了“保险”无条件转 CPU、转 GPU 或转 float32。
- 模型路径、loader 元数据等只读信息应在适配层提取，不要把 UI、队列、持久化状态塞进模型对象。
- 如果 ComfyUI 已有优化 kernel、attention、量化或 cast/offload helper，优先复用，不要重复实现相同底层算子。
- 自定义实现失败时应给出清晰错误；不要静默转换成低质量或不同模型格式。

当前 `模型列表获取`（`XH_ModelSource`）通过 `MODEL.cached_patcher_init` 读取内置 loader 保留的源路径，只生成元数据，不加载模型。无源路径的自定义模型必须仍然可以透传，模型列表输出返回空数组。

## 4. 来源数据与提示词配置

### 4.1 `XH_SOURCE` 数据约定

`XH_SOURCE` 是本工具库内部的通用“来源列表”类型，当前同时承载 LoRA 和基础模型来源。结构如下：

```python
{
    "sources": [
        {
            "source_name": "subfolder/example.safetensors",
            "folder_name": "checkpoints",
            # 以下两个强度字段仅在来源由 LORA_STACK 转换时出现
            "model_strength": 1.0,
            "clip_strength": 1.0,
        }
    ]
}
```

约定如下：

- LoRA 来源默认 `folder_name` 为 `loras`。
- 基础模型来源使用 `checkpoints` 或 `diffusion_models`。
- `source_name` 是相对于对应 ComfyUI 模型目录的路径，不是绝对路径。
- 不把绝对路径、用户目录、设备信息或模型大对象放进来源数据。
- `选择提示词配置` 依靠来源目录和相对路径查找 sidecar；不要在节点中直接读取前端选择状态。
- `core/source_utils.py` 的 `stack_item_to_record` 负责把 dict/tuple 两种 LORA_STACK 元素归一化为 record；新增来源形态时在这一层扩展，而不是在节点里散落兼容代码。

### 4.2 sidecar 文件

当前查找顺序由 `core/config_parser.py` 控制：

1. `模型名.txt`
2. `模型名.json`
3. `模型名.safetensors.json`
4. `模型名.safetensors.txt`

TXT 支持 `正向`、`负向`、`正向2`、`负向2` 等标签；JSON 支持中文或英文 positive/negative 标签。修改解析规则时，必须补充对应 TXT、JSON、空值、重复编号和错误文件测试。

所有来自前端或工作流的目录名、文件名、扩展名都视为不可信输入：

- 只允许固定的 ComfyUI 模型目录映射（`loras`、`checkpoints`、`diffusion_models`）。
- 使用 `folder_paths` 的 resolver 或现有 containment 校验。
- 拒绝绝对路径和包含 `..` 的路径组件（见 `_safe_source_name`）。
- 不通过拼接路径绕过模型目录边界。
- 不接受前端传来的任意目录名后直接调用文件系统。

解析结果统一为 `SourceInspection`（字段 `source_name`、`display_name`、`config_file`、`configs`、`error`、`folder_name`），不再使用历史的 `LoraInspection`/`lora_name`/`model_name` 命名。

## 5. 修改 Python、前端和本地接口

### 5.1 Python 修改

- 先搜索调用方，再修改函数签名或返回值。
- 保持共享函数原有参数顺序、返回类型和异常行为；一次性更新所有调用方时才改变接口。
- 第三方返回值在边界处归一化，核心代码不要到处处理多个 shape 变体。
- import 保持模块级；不要为了“防止出错”大范围增加 `try/except`（节点文件中允许现有“独立运行测试套件”的相对/绝对 import 回退）。
- 删除不再使用的代码，但只删除能够确认无调用方的分支。
- 不新增依赖，除非用户明确要求且现有依赖无法完成任务。

### 5.2 前端修改

前端是原生 ES Module（无打包器），ComfyUI 会递归扫描 `WEB_DIRECTORY`（`./web`）下所有 `.js`；模块缓存保证每个文件只执行一次，因此**只有入口文件允许有副作用（调用 `app.registerExtension`），其余模块只 `export`**。目录按“一节点一模块 + 共享基础设施”组织：

```text
web/
├─ xiheha_toolkit.js     # 唯一入口：registerExtension、按节点 ID 分发 patch、给外部节点装 observer
├─ toolkit.css           # xh-* 样式的可读参考；运行时样式由 shared/styles.js 注入，两者保持同步
├─ shared/               # 跨节点复用、无业务状态
│  ├─ constants.js       # 节点 ID、模型 loader 映射、PORT_LABELS、PREVIEW_INPUTS
│  ├─ styles.js          # 注入用样式字符串（TOOLKIT_STYLES），样式单一来源
│  ├─ dom.js             # 图遍历、widget 工具、最小尺寸、样式注入等通用 DOM/图能力
│  ├─ api.js             # /xiheha_toolkit/inspect 本地只读接口调用
│  └─ upstream.js        # 上游来源采集、依赖图追踪、外部节点变更 observer
└─ nodes/                # 一节点一模块，内聚该节点 controller + patch，导出 NODE_ID 与 patch(nodeType)
   ├─ stack-source.js / model-source.js
   ├─ prompt-selector.js / prompt-preview.js / prompt-merger.js
```

模块依赖必须单向无环：`constants/styles → dom/api/upstream → nodes/* → 入口`；节点模块之间只允许 selector 单向引用 preview 的纯函数（如 `rowToPreviewRow`、`previewHasAllInputsFrom`），反向通过节点实例上的 `__xh*` 鸭子属性解耦，不允许 import 成环。新增节点时照抄 `web/nodes/` 现有模块，并在入口 `NODE_MODULES` 登记一行。

修改前端时必须同时检查：

- `shared/constants.js` 的节点 ID 常量（`XH_StackSource` 等）和 Python 注册 ID 是否一致。
- `PORT_LABELS` 的输入输出数量和 Python 契约是否一致。
- `connectedNode`（`shared/dom.js`）使用的输入名是否真实存在于对应 Python 节点。
- **外部插件节点的端口名不属于本插件，不能随本插件重命名**。例如 easy-use 的 `easy loraStack` 节点，其级联输入端口固定叫 `optional_lora_stack`，`shared/upstream.js` 沿它向上追溯时必须使用该原名；本插件 `XH_StackSource` 自身的输入端口才叫 `stack`。
- 上游模型 loader 的 widget 名（`ckpt_name`、`unet_name` 等）是否真实存在（见 `MODEL_LOADER_SOURCES`）。
- 异步刷新是否存在旧请求覆盖新请求的问题；沿用 selector controller 的 `refreshSequence` 序列号保护。
- UI 状态是否仍能保存到工作流，是否会错误触发采样。
- DOM widget 是否只在对应节点上安装一次（`__xh*Installed` 标记）。
- 前端与后端通信的 payload key 必须一致：执行回传使用 `xh_rows`、`xh_ports`；HTTP 接口路径为 `/xiheha_toolkit/inspect`。

前端只做展示、图遍历和本地接口调用；不要在浏览器中重新加载模型，也不要把模型绝对路径发给前端。

### 5.3 `server.py` 本地接口

- 接口只用于当前 ComfyUI 实例的本地预览，不得增加互联网请求、遥测、统计、更新检查或远程配置。
- 当前唯一路由：`POST /xiheha_toolkit/inspect`，请求体 `{"sources": [{"source_name": ..., "folder_name": ...}]}`，响应体 `{"sources": [SourceInspection.to_dict(), ...]}`。
- 校验 JSON 类型、数组长度（单次上限 100）、字段类型、允许的目录名和路径安全性。
- 错误信息简短、可行动，不返回敏感绝对路径。
- 文件解析异常应被转换为可展示的配置错误，不要让预览接口泄露堆栈或终止 ComfyUI。

## 6. 文件修改与项目管理规则

- 搜索优先，补丁优先。先定位代码，再做最小修改。
- 每次改动只解决当前需求；不要顺便格式化整个文件或重排无关代码。
- 修改前记录工作区状态；不使用 `git reset --hard`、`git checkout --` 或递归删除来“清理现场”。
- 不覆盖用户已有的未提交修改，不删除未跟踪文件，不修改 ComfyUI 主工程文件，除非用户明确要求。
- 保持现有文件布局、节点 ID、工作流连接和模型加载行为。
- 一个功能尽量对应一个小而完整的修改组；代码、必要测试和必要文档可以一起改。
- 不自动提交、推送、创建 PR 或修改外部服务，除非用户明确要求。
- 版本号只在用户可见行为发生变化时更新；同时更新 `CHANGELOG.md`。
- README 只记录实际支持的行为、连接方式、配置格式和限制，不写未验证的承诺。

## 7. 更新实施流程

每次功能新增、修复或重构都按下面的顺序进行：

### A. 了解现状

- 阅读本文件和相关源码。
- 搜索所有调用方、注册点、前端引用和测试。
- 检查工作区已有改动。
- 明确哪些行为必须保持不变。

### B. 设计最小改动

- 明确输入、输出、数据结构、错误行为。
- 选择唯一的责任层。
- 列出需要增加或修改的最少文件。
- 明确不支持的情况和安全边界。

### C. 实现

- 先写或补充关键回归测试，再写最小实现也可以；但最终代码和测试必须同时完成。
- 使用现有 helper 和本地风格。
- 不引入远程请求和无关依赖。

### D. 验证

- 先跑针对性测试，失败时修实现，不要删测试或放宽断言。
- 再跑完整测试和编译/语法检查。
- 涉及节点注册时验证注册表和导入。
- 涉及前端时运行 JavaScript 语法检查。
- 涉及模型路径时测试 checkpoint、diffusion model、嵌套目录、缺失源路径和路径穿越输入。

### E. 文档和交付

- 更新 README 和 CHANGELOG（若行为对用户可见）。
- 再次检查实际修改文件和差异。
- 报告实现内容、测试命令及结果、未验证的部分和使用限制。

## 8. 测试与验收

### 8.1 自动测试

当前 Windows 工作区优先使用随项目提供的 Python：

```powershell
$env:PYTHONPATH = "E:\HuiShi_launcher-WorkFisher-V2\ComfyUI"
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" -m unittest discover -s tests
```

至少执行：

```powershell
$py = Get-ChildItem __init__.py,server.py,core\*.py,nodes\*.py | ForEach-Object { $_.FullName }
& "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" -m py_compile @py
Get-ChildItem -Recurse web -Filter *.js | ForEach-Object { node --check $_.FullName }
```

如果机器没有上述路径，使用当前环境可用的 Python，并确保 ComfyUI 根目录在 `PYTHONPATH` 中。不要因为运行环境不同而跳过测试；如果确实无法运行，必须在交付说明中明确写出。

### 8.2 节点功能验收

新增或修改节点至少验证：

- 节点能被 ComfyUI 导入并出现在搜索结果中。
- `INPUT_TYPES`、`RETURN_TYPES`、`RETURN_NAMES`、`FUNCTION` 和实际返回值一致。
- 透传对象保持同一对象引用，除非需求明确要求 clone。
- 空输入、缺失元数据、缺失配置文件和错误配置不会产生静默错误。
- 新节点不会重新加载模型、改变 dtype/device 或增加无关显存占用。

### 8.3 前端和工作流验收

涉及前端时，在 ComfyUI 中重启或重新加载插件并刷新浏览器，然后验证：

1. 节点名称和端口名称正确。
2. Checkpoint/UNet loader → `模型列表获取` → 采样器连接正常。
3. `模型列表获取` 第二路 → `选择提示词配置` 能显示配置。
4. easy-use `easy loraStack` → `easy-use兼容_模型列表获取` → `选择提示词配置` 的 LoRA 流程正常，包括 easy-use 自身的 `optional_lora_stack` 级联。
5. 修改上游模型/LoRA 后选择器会刷新，不会被旧异步请求覆盖。
6. 选择状态能保存，重新打开工作流后不丢失。
7. 没有配置或无法识别源路径时，界面显示清晰提示，模型执行仍不被无故阻断。

## 9. 常见错误与禁止做法

- 只改 Python 注册，不改前端节点 ID 常量，造成端口标签或动态 UI 不工作。
- 只改前端扫描逻辑，不改 Python 执行逻辑，导致预览能显示但队列执行结果为空。
- 重命名本插件端口时，误改外部插件（如 easy-use）的端口名，导致上游追溯断裂。
- 用模型对象的类名猜文件名，而不是读取 loader 保留的 `cached_patcher_init` 源信息。
- 将绝对路径直接放入工作流、HTTP 响应或前端状态。
- 在节点中重新加载 checkpoint、复制模型、修改模型内部属性或管理显存。
- 用 `getattr` 随意探测子对象属性来决定跨层业务流程；需要能力标志时，应在拥有该能力的边界显式提供。
- 为了让测试通过而删除旧断言、吞掉异常或把所有输入转换成字符串。
- 一次性重写整个文件、升级依赖、清理缓存或删除看似无关的代码。
- 增加任何联网、遥测、统计、更新检查、授权检查、崩溃上报或远程配置。

## 10. 交付报告模板

完成后向用户简要报告：

```text
已完成：
- 修改了哪些行为和文件
- 新增/更新了哪些测试

验证：
- 测试命令：...
- 结果：通过/失败（附关键错误）
- 是否完成 ComfyUI 手工连线验证

限制或后续：
- 仅记录真实存在、尚未解决或尚未验证的问题
```

不要声称执行过没有实际执行的测试，也不要把“理论上可行”写成“已验证”。
