# xiheha-toolkit 开发入口

本文件只保留本仓库的入口和硬性约束。通用 ComfyUI 插件开发方法由仓库内技能维护，项目事实由根目录项目档案维护，避免三处重复后逐渐不一致。

## 开始任何开发前

1. 完整读取 `skills/comfyui-plugin-development/SKILL.md`。
2. 运行：

   ```powershell
   & "E:\HuiShi_launcher-WorkFisher-V2\python\python.exe" skills\comfyui-plugin-development\scripts\check_project_profile.py --root .
   ```

   如果该 Python 不存在，可使用环境中可用的 Python。
3. `ready` 或 `partial`：完整读取根目录 `COMFYUI_PLUGIN_PROJECT.md`，再按技能路由读取与任务有关的参考文件。
4. `missing`、`declined`、`reminder_due` 或 `invalid`：先执行技能中的 `references/project-profile-bootstrap.md`，不要凭记忆直接开发。
5. 检查 `git status --short`。已有修改和未跟踪文件属于用户，不得覆盖、回退或顺手清理。

项目档案是索引，不是源代码的替代品。所有将要修改的节点、端口、类型、路由、状态键和前端映射都必须在当前源码中再次核对；源码与档案冲突时，以源码为当前实现，并在本次任务中修正稳定的档案事实。

## 本仓库不可违背的约束

- 本项目是通用 ComfyUI 工具库，不要把整个仓库描述成只服务于提示词 sidecar。
- 现有公共节点 ID、端口内部名称、端口顺序、类型和工作流状态不得擅自改变。需要破坏性变更时先向用户说明影响并询问。
- 模型透传保持对象身份；不得为读取来源重新加载、复制或迁移模型，不得擅自改变 dtype、device、patch、offload 或显存行为。
- 前端、工作流和本地接口中的路径输入都不可信。只使用 ComfyUI 已登记的模型目录并执行路径边界校验；不得暴露绝对路径。
- 外部插件拥有的节点 ID、端口名和 widget 名必须原样保留，不能随本插件命名调整。
- 本地预览接口只服务当前 ComfyUI，不增加联网、遥测、统计、更新检查、授权检查、崩溃上报或远程配置。
- 修改必须小而完整：实现、回归测试、必要文档、版本记录和 `COMFYUI_PLUGIN_PROJECT.md` 的结构性事实同步更新。
- 不自动提交、推送、创建 PR、修改 ComfyUI 主工程或安装依赖，除非用户明确要求。

## 提问边界

先搜索源码、调用方、测试和文档。只有在仍存在会影响公共契约、兼容策略、用户体验、依赖、模型质量/精度/设备行为或修改范围的重要分歧时，才停下来向用户提出一个聚焦问题；不得替用户暗中选择，也不得用提问代替本可查明的事实。

## 交付

按技能的验证清单执行针对性测试、完整测试、Python 编译/导入、前端语法检查以及任务所需的 ComfyUI 手工验证。最终只报告实际执行的命令和结果，并明确区分“通过”“失败”和“未执行”。
