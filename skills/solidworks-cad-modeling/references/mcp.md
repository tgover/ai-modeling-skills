# SolidWorks MCP 工作流

## 已集成项目与配置发现

使用 [wzyn20051216/solidworks-automation-skill](https://github.com/wzyn20051216/solidworks-automation-skill) 的本地 Python STDIO MCP。2026-10-20 按 GitHub 搜索 `solidworks mcp` 的星标排序，它在包含 MCP 的相关工具包中为首位（1,311 星）；这是检索时快照，不是固定排名承诺。安装源码快照为 `5dd71909985ba10e3265aac64dbb9185d8276813`，MIT 许可证保留在上游目录。实际握手返回 66 个工具，以现场 `tools/list` 为准。

安装位置属于本机配置，不写死在可复用技能内。读取 `$CODEX_HOME/config.toml`，未设置时读取 `~/.codex/config.toml`，只提取 `[mcp_servers.solidworks]`：

- `command`：独立环境的 Python。
- `args`：上游 `mcp-server/server.py`；其父目录的父目录即上游根目录。
- `env.SW_MCP_OUTPUT_ROOT`：当前允许取回产物的根目录；任务文件保存到用户指定项目内。
- `env.SW_MAX_DOCUMENTS`：本机文档预算。装配体加载的零件也可能计入；不要为了测试关闭用户文档。遇到 `SW_DOCUMENT_BUDGET` 时先读文档数量，按任务需要有限提高预算，或只关闭本轮自建文档。

不读取或输出配置中无关的凭据。不要运行上游多客户端注册器；当前任务只配置 Codex。更新上游时先保存源码版本及依赖清单，再按本机版本重新验收。

## 连接与建模

1. 运行 `solidworks_health_check`；然后 `solidworks_connect`，检查返回版本与当前文档身份。连接可能启动 SW；所有 COM 建模操作串行执行，避免多个代理或客户端同时操作一个桌面会话。
2. 新模型建立新文档；修改已有模型前核对路径与文档类型。保存当前文档清单和活动文档。禁止用 `close_all=true` 清理验收环境；只关闭已确认属于本轮的文档。
3. 按当前工具 schema 调用。此项目通常使用 `{"params":{...}}` 包装；长度字段 `_mm` 为毫米，角度字段 `_deg` 为度。底层 SW COM 通常用米与弧度，需要明确转换。中文默认基准面可用 `前视基准面`；上游基础工具也有英文名称别名处理。
4. 支持时使用原生草图、拉伸、孔、圆角、阵列、镜像和装配工具。先读实际边列表，再按几何选边；更改几何后重新读取，不复用过期边索引。超出工具覆盖时阅读相应上游模块并编写任务脚本，不把网格替代为原生可编辑零件。
5. 每步检查工具内部 JSON 的 `status`、错误、`feature_created`、保存和重建结果。MCP 外层 `isError=false` 或脚本退出码 0 不能替代这些检查。`blocked`/`error`/`failed` 停在首个错误；`review_required`/`warn` 表示仍需复核，不能直接写成验收通过。
6. 用 `solidworks_mass_properties`、`solidworks_bounding_box`、`solidworks_review_active` 和原生特征树检查尺寸、体积、实体数、关键位置与可编辑性。不要为只读测量传入密度覆盖，它会修改文档密度。
7. `solidworks_save_document` 保存原生文件，`solidworks_export_active` 导出所需格式。保存后关闭本轮文档并重开检查；STEP 再导入验证单位、实体数、尺寸和体积。STEP 导入后 `GetPathName` 可能为空，凭本轮返回的对象/标题与文档快照确认身份，必要时另存到新的测试路径再验证。
8. 检查实际生成的预览图。测试完成恢复先前活动文档，保留用户原有文档与未保存状态。

## 按任务阅读上游资源

从配置解析上游根目录后，按实际需要读取；这些是参考资料，当前用户要求和本技能的验证边界优先。

| 任务 | 上游相对路径 |
|---|---|
| 当前能力与版本限制 | `capabilities.yaml`、`mcp-server/README.md` |
| 草图、特征、语义选边 | `references/part-modeling.md`、`references/edge-selection.md` |
| 孔槽与真实内螺纹 | `references/complex-hole-features.md`、`subskills/solidworks-threaded-holes/README.md` |
| 装配、导出、复核 | `references/assembly.md`、`references/export.md`、`references/review.md` |
| 工程图 | `references/drawing.md`，按需安装 PDF 复核依赖 |
| 未覆盖 API、连接失败 | `references/api-lookup.md`、`references/troubleshooting.md` |

上游当前主要验收目标为 SW2026；本机已通过 SW2024 的基础链路，不能据此宣称所有上游能力在 SW2024 已验证。没有安装 OCCT、FEA、网格或 PDF 可选依赖时，只对当前任务确需的依赖按需配置。

## 尚未刷新 MCP 工具目录时

安装配置后，新一轮对话通常重新加载工具；未出现时重启客户端。当前轮可用 `scripts/sw_mcp_client.py` 验证已配置的本地服务。使用 MCP 环境中的 Python（包含 `mcp` SDK，且此帮助脚本需要 Python 3.11+）：

```powershell
& $mcpPython (Join-Path $taskSkill 'scripts/sw_mcp_client.py') --list
& $mcpPython (Join-Path $taskSkill 'scripts/sw_mcp_client.py') --tool solidworks_health_check
& $mcpPython (Join-Path $taskSkill 'scripts/sw_mcp_client.py') --tool solidworks_create_basic_part --arguments-file $taskArguments
```

参数文件是工具完整 JSON 入参，例：

```json
{"params":{"shape":"box","width_mm":60,"height_mm":40,"depth_mm":10,"output_path":"<当前任务的新绝对路径>.SLDPRT"}}
```

替换输出路径后再执行。帮助脚本允许调用服务器工具，写操作仍须属于当前用户任务；它不是只读诊断的统一入口。不要和另一个正在建模的 MCP 客户端并用。

## 本机验收边界

2026-10-20，SW2024 SP5（32.5.0），Python 3.12，MCP SDK 1.30：60 × 40 × 10 mm 原生草图拉伸盒体验收通过；原生保存重开和 STEP 重导入均为一个实体、24,000 mm³，四视图预览已生成。真实重建、体积、尺寸及 STEP 文件都经过回读。高级机械特征、装配配合、工程图和仿真须在各自任务中另验；随包 VBA 底板例程仍未实机编译验证。详细本机日志保存在任务项目，不能提交到公共技能源码。
