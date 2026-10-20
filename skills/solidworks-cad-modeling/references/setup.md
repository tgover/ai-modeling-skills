# 新电脑安装和 SW 验收

## 先准备软件

使用 Windows 桌面版 SolidWorks。遵循已有软件版本；本技能以 SW2022 API 为基线，不要求为了使用 AI 建模而换版本。先确认软件本身能新建、保存零件，并能打开“工具 → 宏 → 新建/编辑/运行”。许可证和软件安装包由用户通过相应渠道准备，技能不包含它们。

生成 VBA 源码只需要 Python 标准库，也可以由 AI 按图纸直接编写宏。可选的自动读取和运行工具需要 Python 3 与 pywin32。在独立 Python 环境中安装 `references/requirements.txt`；不要求安装 MCP。

使用 `$skill-installer` 从仓库 `tgover/ai-modeling-skills` 的 `skills/solidworks-cad-modeling` 路径安装到个人技能目录，即可在多个项目调用。具体发现目录以当前客户端为准；安装后下一轮对话使用，未发现时重启客户端。

## 检查连接

手动打开 SolidWorks，关闭模态对话框，保持 Python 与 SW 使用相同 Windows 用户和权限。运行：

```powershell
& $taskPython (Join-Path $taskSkill 'scripts\sw_status.py')
```

将 `$taskSkill` 设为技能实际安装目录，`$taskPython` 设为当前电脑环境的 Python。默认连接 `SldWorks.Application`；多版本环境可设置 `SOLIDWORKS_PROGID`，例如对应版本注册的 ProgID，必须以本机注册结果为准。

返回 `not_registered` 时，检查是否在这台电脑安装了桌面 SW、版本是否正确注册。返回 `connection_failed` 时，检查软件是否已打开、是否有弹窗以及用户/权限是否一致。不要将这些结果改写为“已连接”或自动更改注册表。`connected_read_only` 仅表示读到了软件，不等于验证了建模。

## 首次完整验收

1. 在目标电脑找到实际零件模板 `.prtdot`，并确认该模板能手动新建零件。不要复制源电脑的绝对路径。
2. 选择当前项目下新的空测试输出目录。生成合成验收件源码：

```powershell
& $taskPython (Join-Path $taskSkill 'scripts\generate_plate_macro.py') --output $taskTestOutput --part-template $taskPartTemplate
```

这两个变量分别是新测试目录和目标电脑的模板路径。默认底板为 200 × 120 × 20 mm，四个直径 24 mm 的孔，孔中心距相邻边 30 mm。源文件 `plate.bas` 和 `parameters.json` 并不表示已生成三维模型。

3. 在 SW 中“工具 → 宏 → 新建”，新建并保存 `.swp` 到测试目录。在 VBA 编辑器的标准模块中，用 `plate.bas` 的完整内容替换该模块原代码。入口是 `Sub main()`，记录实际模块名。源文件是 ASCII，中文路径通过 `ChrW$` 表达，避免源码导入时把路径转成乱码。
4. 编译并运行宏。也可保存后使用以下可选工具运行；模块名以 VBA 编辑器中实际名称为准：

```powershell
& $taskPython (Join-Path $taskSkill 'scripts\run_macro.py') --macro $taskMacroProject --module $taskModuleName
```

`$taskMacroProject` 必须指向真实 `.swp`。`.bas` 不能改扩展名冒充 `.swp`，运行工具也不会替你创建宏工程。

5. 检查 `validation.txt` 中的状态、SW 修订版本、实体数、体积和保存警告；任何警告都应核对。运行工具的 `macro_invoked` 只表示调用成功，不代表宏内部通过了所有检查。
6. 重新打开 `plate.SLDPRT`，确认原生草图与拉伸特征、板尺寸、四孔位置与贯穿性。重新导入 `plate.step` 检查尺寸、单位、实体数；检查等轴测和正交视图，并保存预览。全部通过后才把目标电脑的“真实建模/导出验收”记录为通过。

示例草图按坐标生成，未完全标注尺寸约束；它用于软件连接和保存链路验收。正式参数化零件应添加实际尺寸、关系和必要的完全约束。示例体积检查也不能替代孔位和完整特征检查。

## 当前发行验证范围

初次发行时，只在没有可用 SW COM 注册的电脑上验证了 Python 源码生成、参数校验、中文路径处理、拒绝覆盖及不可用环境诊断。未在真实 SW 中完成 VBA 编译、建模、保存和 STEP 重导入。发现运行兼容问题时，保留失败的宏、软件修订版本和首个错误，在目标 SW 版本上修复后再更新技能。
