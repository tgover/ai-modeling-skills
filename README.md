# AI 建模技能库

集中维护用于不同建模软件的个人 AI 技能。在每台电脑安装一次个人技能，即可在多个项目中调用；模型和图纸保存在各自项目。

仓库：[tgover/ai-modeling-skills](https://github.com/tgover/ai-modeling-skills)

## 按软件选择技能

| 软件 | 技能与安装路径 | 使用方式 | 验证范围 |
|---|---|---|---|
| Blender | [blender-cad-modeling](skills/blender-cad-modeling/SKILL.md) / `skills/blender-cad-modeling` | CAD/参考图 → 本地脚本 → `.blend`、GLB/STL、预览 | 已在初次发行 Windows 环境验证建模、保存重开、渲染、导出与单位；新电脑仍需自检 |
| SolidWorks（SW） | [solidworks-cad-modeling](skills/solidworks-cad-modeling/SKILL.md) / `skills/solidworks-cad-modeling` | 图纸/参考图 → 已配置 MCP、COM 或 VBA → 原生特征与 SLDPRT/SLDASM、按需 STEP | SW2024 SP5 的 MCP 基础盒体、原生保存重开和 STEP 重导入已验收；高级特征、装配、工程图及随附 VBA 仍需实机验证 |

不同软件保留各自的 API、原生格式和验证要求。技能会针对具体任务生成建模代码，随附的简单示例不能自动还原所有复杂图纸或照片。

SW 建模默认保留拉伸、切除等原生特征，并按实际零件结构建立装配：普通零件不含无关联的悬浮实体，相同规格重复件复用同一零件文件，通过组件实例/阵列与真实配合完成装配。交付前检查连接、支撑、意外自由度和引用关系，详见 [SW 建模规范](skills/solidworks-cad-modeling/references/modeling.md)。这是建模与验收要求，不扩展现有实机验证范围。

## 在任意电脑安装

1. 在目标电脑安装 Codex 和要使用的建模软件。
2. 在 Codex 中请求 `$skill-installer` 从本仓库安装所需路径到**个人技能目录**。例如：

   > 使用 $skill-installer，从 https://github.com/tgover/ai-modeling-skills 安装 skills/solidworks-cad-modeling 到个人技能目录，让不同项目都能调用。

   Blender 对应路径为 `skills/blender-cad-modeling`；也可一次指定这两个路径。

3. 下一轮对话中，让 AI 读取相应技能的 `references/setup.md`，配置本机环境并执行该软件的验收。未发现新技能时重启客户端。
4. 在实际项目中发图纸、图片和建模需求，显式选择 `$solidworks-cad-modeling` 或 `$blender-cad-modeling`，或让 AI 根据需求选择已安装的技能。

软件、许可证、Python 环境和模板需在各台电脑配置；仅登录同一 GPT 账号不能替代本地安装。两项技能都不强制要求 MCP，也不要求建模服务 API Key。公开仓库可直接读取，更新后仍需更新各电脑的安装副本。

SW 技能已整合 [solidworks-automation-skill](https://github.com/wzyn20051216/solidworks-automation-skill) 的 MCP 调用与专项参考路由，入口仍为 `$solidworks-cad-modeling`。使用 MCP 的电脑需单独安装上游及其独立 Python 环境，并注册 Codex 的 `solidworks` 服务；详见 [MCP 工作流](skills/solidworks-cad-modeling/references/mcp.md)。2026-10-20 基础验收件为 60 × 40 × 10 mm、一个实体、体积 24,000 mm³，原生文件重开及 STEP 重导入一致；该结论不扩展到全部上游功能。

## 目录和维护规则

```text
skills/
  blender-cad-modeling/
  solidworks-cad-modeling/
catalog.json             按软件列出的安装路径和验收状态
tests/                   不依赖建模软件的包级检查
AGENTS.md                后续添加建模技能的约定
```

今后 AI 建模相关技能统一维护在本仓库，以软件名区分技能目录。新增软件时，添加 `skills/<software>-<workflow>/`，更新本页和 `catalog.json`，保留已有安装路径。每项技能独立包含入口、必要脚本与资源、环境配置和验收说明。

本仓库分发可复用源码与说明，不上传私人图纸、客户模型、软件安装包、许可证、凭据或某台电脑的固定配置。测试必须区分源码检查、软件连接和真实建模验收；没有对应软件时明确记录未验证部分。

维护者更新建模技能并完成相应检查后，在同次任务中及时提交并推送 GitHub，同步维护本页与 `catalog.json`，核对远端提交后提供链接。同步个人安装副本时保留发行版的跨电脑配置机制，排除本机配置和私有资料；发布失败时明确说明尚未同步的改动。
