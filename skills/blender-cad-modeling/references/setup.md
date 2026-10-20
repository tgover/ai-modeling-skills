# 新电脑配置与跨项目调用

本技能使用本机 Blender 后台脚本创建模型，不需要 Blender MCP、建模服务 API Key 或常驻控制端口。每台电脑配置一次；模型和图纸留在当前工作项目。

## 安装位置

使用 Codex 内置 `$skill-installer` 从 GitHub 仓库的 `skills/blender-cad-modeling` 路径安装到个人技能目录，随后在新一轮对话中调用。若客户端仍未发现技能，重启客户端。

当前技能安装器默认使用 `$CODEX_HOME/skills`，未设置时为 `~/.codex/skills`。不同版本客户端的发现目录可能不同；新版文档还列出 `~/.agents/skills`。以目标客户端内置安装器和实际技能列表为准，避免在多个发现目录同时安装同名技能。

## 配置软件和 Python 依赖

1. 安装 Blender。若已安装，先确认实际可执行文件的位置。此包不分发 Blender、AutoCAD 或 LibreDWG 二进制文件。
2. 使用 Python 3.12 新建独立虚拟环境。不要复制其他电脑的 `.venv`，不要把宿主 Python 的依赖路径加入 Blender 内置 Python。
3. 用这个虚拟环境安装技能中 `references/requirements-lock.txt` 的依赖。
4. 用这个虚拟环境执行 `scripts/configure.py --blender '<blender.exe 实际路径>'`。
5. 执行 `scripts/configure.py --check`。只有依赖检查通过后，运行 `scripts/selftest.py --output '<新的空测试目录>'`。

例如，在 PowerShell 中先将 `$taskSkill` 设为实际安装的技能文件夹，再执行：

```powershell
$taskEnv = Join-Path $env:USERPROFILE '.codex\environments\blender-cad'
py -3.12 -m venv $taskEnv
$taskPython = Join-Path $taskEnv 'Scripts\python.exe'
& $taskPython -m pip install -r (Join-Path $taskSkill 'references\requirements-lock.txt')
& $taskPython (Join-Path $taskSkill 'scripts\configure.py') --blender $taskBlender
& $taskPython (Join-Path $taskSkill 'scripts\configure.py') --check
& $taskPython (Join-Path $taskSkill 'scripts\selftest.py') --output $taskTestOutput
```

运行前，将 `$taskBlender` 设置为实际 Blender 可执行文件路径，将 `$taskTestOutput` 设置为当前项目下一个新的测试输出目录。若环境已存在，先确认其版本和依赖，避免无意改变已有环境。

配置写入 `$CODEX_HOME/environments/blender-cad/config.json`，默认是 `~/.codex/environments/blender-cad/config.json`，与技能源文件分开，重新安装技能不会删除该配置。`configure.py` 返回该电脑的实际配置路径。`--check` 只检查，不写入。

配置加载优先级从低到高：随包示例、旧版技能内 `references/local-environment.json`（如果存在）、个人环境配置、环境变量。可通过 `BLENDER_CAD_CONFIG` 指向另一份现有 JSON 配置；没有该变量时才会使用默认配置路径。

可执行文件覆盖变量：`BLENDER_EXECUTABLE`、`BLENDER_CAD_PYTHON`、`LIBREDWG_DWG2DXF`、`LIBREDWG_DXF2DWG`、`AUTOCAD_CORE_CONSOLE`。从 PATH 和 Windows 标准安装目录自动发现 Blender 只是便利功能；存在多个版本时请明确指定。

## 可选 DWG 支持

DWG 输入需要独立安装、验证转换器；优先 LibreDWG。使用官方发行的 Windows 工具，并保留下载来源和版本。配置命令示例：

```powershell
& $taskPython (Join-Path $taskSkill 'scripts\configure.py') --dwg-converter $taskDwg2Dxf --dwg-writer $taskDxf2Dwg
& $taskPython (Join-Path $taskSkill 'scripts\check_dwg.py') --backend libredwg --output $taskDwgTestOutput
```

将这三个变量设置为实际工具路径和新的空测试目录。`dwg_writer` 仅为合成 DWG 往返测试所需，日常 DWG → DXF 转换只需要 `dwg_converter`。没有转换器时，可以先提供 DXF，其他模型创建能力不受影响。

## 验证与使用

`selftest.py` 检查合成 DXF 的单位、曲线和图层，PDF 与图片读取，Blender 建模、保存与重开，GLB 米单位、STL 毫米单位、四个通孔、封闭性、体积和预览图。查看测试目录中的 `validation.json` 和 `preview.png`。这个合成测试不代表任意复杂 CAD 都可以无损还原。

在任意项目里可以直接说：

> 使用 $blender-cad-modeling，根据这些图纸和参考图片建立新模型。尺寸以图纸为准，输出到当前项目，交付可编辑的 Blender 文件和预览图。

更新技能时只替换技能源文件，保留个人环境配置；之后复查依赖并运行自检。GitHub 源文件更新不会自动更新已安装的副本。
