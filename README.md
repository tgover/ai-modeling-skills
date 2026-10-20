# Blender CAD 建模个人技能

把经过本地验证的 CAD 与参考图 Blender 建模流程保存到 GitHub，供自己在不同电脑、不同项目中调用。

技能仓库：[tgover/ai-modeling-skills](https://github.com/tgover/ai-modeling-skills)

## 能做什么

- 根据 DXF、PDF 图纸和参考图片，按尺寸创建可编辑 Blender 模型。
- 配置独立转换器后处理 DWG。
- 保存 `.blend`，按需导出 GLB、STL 并渲染预览。
- 校验尺寸、单位、通孔、网格封闭性和输出比例。

技能依赖本机 Blender 和 Python 环境。无需 Blender MCP 或建模 API Key。网格导出不是 STEP/BREP 工程实体；需要 STEP 或 Revit/IFC 时应另选对应建模、校验流程。

## 在另一台电脑安装

1. 在新电脑安装 Codex，登录账号。
2. 在 Codex 中发送：

   > 使用 $skill-installer，从 https://github.com/tgover/ai-modeling-skills 安装 skills/blender-cad-modeling 到个人技能目录，让我能在不同项目中调用。

3. 私有仓库需要先在新电脑完成 GitHub/Git 登录，账号登录本身不会授予仓库访问权限。
4. 下一轮对话中告诉 Codex：

   > 请使用 blender-cad-modeling 技能的 references/setup.md，检查并配置本机 Blender 与 Python 依赖，调整本机路径，并运行建模自检。验证通过后在当前项目创建新的模型。

每台电脑配置一次软件和依赖。个人技能可在多个项目中被发现，也可以显式使用 `$blender-cad-modeling`。安装到某一个项目的技能目录则只在该范围内使用。具体发现目录以目标客户端为准。

## 仓库内容

```text
skills/blender-cad-modeling/
  SKILL.md
  agents/openai.yaml
  references/
    setup.md
    local-environment.example.json
    requirements-lock.txt
  scripts/
    configure.py
    run_blender.py
    cad_prep.py
    blender_tools.py
    selftest.py
    smoke_scene.py
    check_dwg.py
```

本仓库只包含可复用技能、脚本和依赖版本，不包含历史任务、工程图纸、模型、软件安装包或用户凭据。本机安装路径保存在个人环境配置中，不提交到仓库。

技能更新后，其他电脑需要手动更新安装副本，并复查依赖和自检。初次发行在 Windows 上验证；其他系统需要适配并验证路径及外部工具。
