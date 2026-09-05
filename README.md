# ComfyUI-xiheha-toolkit

ComfyUI 自定义节点**工具库**（`xiheha-工具箱`），当前模块为「模型来源提示词配置」：读取模型 / LoRA 同目录 sidecar 的 TXT/JSON 提示词配置，支持来源采集、配置选择、词条开关预览与提示词合并。

## 节点

| 节点 | 说明 |
| --- | --- |
| 模型列表获取 | 透传 `MODEL`，输出模型来源列表 |
| easy-use兼容_模型列表获取 | 透传 easy-use `LORA_STACK`，输出模型列表 |
| 选择提示词配置 | 扫描 sidecar 配置，选择正向/负向提示词 |
| 模型提示词控制 | 按词条启用/关闭提示词，实时预览 |
| 提示词合并 | 按端口顺序合并最多四段提示词 |

## 效果预览

![工作流示例](workflow-example.png)

## 安装

复制到 `ComfyUI/custom_nodes/xiheha-toolkit`，重启 ComfyUI 并刷新浏览器页面。

## 配置格式

在模型 / LoRA 同目录放置同名 TXT 或 JSON 文件，按以下顺序查找：`模型名.txt`、`模型名.json`、`模型名.safetensors.json`、`模型名.safetensors.txt`。

```text
正向：anime face, realistic hair,
负向：lowres, watermark,
正向2：another style,
负向2：bad anatomy,
```

详细开发规范见 `AGENTS.md`。
