# Blender 交付检查与 Codex 钩子

本流程把检查绑定到具体文件版本。适用于新建或修改 Blender 模型；只读问答、技能维护及测试模型不登记为交付物。旧模型不会被扫描或批量修改。当前没有 SolidWorks 检查适配器，不能用此报告替代 SW 原生装配验收。

## 工作方式

1. 建模前在任务目录建立验收单，记录当前 `.blend` 输出路径、实际物件、关键尺寸、数量、连接、支撑和需要看图的内容。区分已确认尺寸与估计，不能事后按错误模型改写目标。
2. 使用钩子提供的**当前 session_id** 登记本次任务及每个交付物。一个任务保持同一个 `task-id`，多交付物分别登记；再次登记同一任务不清空修复次数。只有用户明确开始新任务时才换 task-id。
3. 每次形成拟交付版本，先保存，再运行 `validate`。它用独立后台 Blender 重开文件，只在内存中检查，不保存、不改写原模型。首次运行可能因尚无看图记录而未通过，这不妨碍查看几何检查结果。
4. 打开并查看与当前模型对应的总览、局部及要求的参考对照图；核对验收单中的 `review_topics`，修复发现的问题。看图后执行 `record-review`，写明观察结果及仍有的问题，再运行 `validate`。
5. 交付前 Stop 钩子复查报告、模型、验收单、检查程序、看图记录和图片的 SHA-256。任何文件变化、检查失败、缺少证据都要求继续处理。最多发出 3 次修复请求，连续两次修复后无进展会提前停止；随后仅要求如实汇报未通过项，避免无限续跑。

```powershell
& '<host-python>' -X utf8 '<skill>/scripts/model_qa.py' register --root '<project>' --session '<current-session-id>' --task-id '<this-modeling-task>' --contract '<task>/acceptance.json'
& '<host-python>' -X utf8 '<skill>/scripts/model_qa.py' validate --contract '<task>/acceptance.json'
& '<host-python>' -X utf8 '<skill>/scripts/model_qa.py' record-review --contract '<task>/acceptance.json' --view 'overview=<overview.png>' --view 'detail=<detail.png>' --note '<what was actually inspected>'
& '<host-python>' -X utf8 '<skill>/scripts/model_qa.py' validate --contract '<task>/acceptance.json'
```

有未解决问题时，`record-review` 添加 `--finding '<issue>'`，它会保持未通过。不能在没有查看图片时登记已审阅，也不能复用不属于当前模型的旧效果图。图片可解码和内容哈希只证明文件完整，不证明画面确实符合参考，仍需要实际看图。

用户中断时 Interrupt 钩子暂停该任务，不继续修复。用户明确恢复后，以同 task-id 登记并添加 `--resume`；它保留原修复预算。某次检查已通过后再修改模型，必须重新形成有效证据。

## 验收单

复制 [示例验收单](../assets/quality-contract.example.json)，按实际项目填写。文件路径相对验收单所在目录；坐标以米表示，尺寸和接触间隙以毫米表示。`model_kind` 为 `general`、`equipment` 或 `piping`。

| 字段 | 含义与实际检查 |
|---|---|
| `objects` | 实体名称/名称通配符，覆盖活动场景中的所有交付几何；缺物件、空几何和非有限坐标失败 |
| `excluded_objects` | 每项包含 `object`、`reason`；只用于说明参考线、施工辅助等排除项，不能掩盖交付实体 |
| `dimensions` | 每项包含 `objects`、`expected_mm` 三轴尺寸和 `tolerance_mm`；按求值后世界坐标量测 |
| `counts` | 每项包含 `objects`、`expected`；核对匹配物件数量 |
| `connected_parts` | 每项包含 `object`、`expected`；核对网格连通岛数量，不把任意接触认作机械连接 |
| `connections` | 每项 `a`、`b` 各含物件名 `object`、局部 `point_m`、局部 `axis`；核对世界坐标端口间距和轴向 |
| `contacts` | 每项 `a`、`b`、`max_gap_mm`，检查声明的实际安装对；用双向顶点到三角面距离及面相交判断，不能代替完整支承选型 |
| `collision_objects` | 要检查的物件集合。先按包围盒初筛，再用 Blender EXACT 布尔交集体积检查候选，包含完全包容；超过 0.01 mm³ 判为相交。检查对象须为闭合实体，开口几何不能被称为已完成实体干涉验收 |
| `allowed_intersections` | 每项为一个明确物件对 `a`、`b` 及 `reason`；禁止整类豁免 |
| `bore_paths` | 每项含 `objects`、世界坐标折线 `points_m` 及 `sample_radius_m`；每段中心及四条偏移射线检查堵塞，起终点放在需检查开口的外侧。是抽样几何检查，不证明完整内腔或水力性能 |
| `overview` | 可指定默认 `scene` 和需要可见的 `objects`。检查隐藏、相机/局部/锁定视图、居中距离及裁剪；距离检查较保守，画面是否完整仍由实际看图确认 |
| `required_views` | 必须看图的角色，默认 `overview`、`detail`；参考复建再加入 `reference` 并提供同视角对照 |
| `review_topics` | 当前项目需要判断的原理、细节、材质、品牌、支承和参考差异等，必须在实际看图记录中覆盖 |
| `assumptions` | 图片估计、隐藏结构补全、非实时屏幕内容及其他未确认项 |

所有模型至少包含尺寸与干涉对象集合；管路模型还必须有端口、安装接触和内腔抽样检查。示例端口配置：

```json
{
  "a": {"object": "Pipe_A", "point_m": [0.5, 0, 0], "axis": [1, 0, 0]},
  "b": {"object": "Pipe_B", "point_m": [-0.5, 0, 0], "axis": [-1, 0, 0]},
  "max_gap_mm": 0.5,
  "angle_tolerance_deg": 1,
  "opposed_axes": true
}
```

报告只覆盖验收单中的几何和安装关系。遗漏的物理语义不会凭空被识别：所有几何虽须列入物件清单，仍要按实际系统补齐关键关系，不能只写一个外箱尺寸来代表整机通过。容差按图纸/用途确定，单位、边界和推定性质写清。承载、水力、换热及控制策略等需要对应资料和专项计算。

## 安装到项目

```powershell
& '<host-python>' -X utf8 '<skill>/scripts/model_qa.py' install-hooks --project '<project>'
```

安装器合并项目 `.codex/hooks.json`，保留其他钩子并备份原文件。注册 `SessionStart`、`UserPromptSubmit`、`Stop`、`Interrupt`，不修改全局配置、不启动常驻服务、不改信任记录。安装前确认当前 Codex 的 hooks 功能可用。

**启用仍需用户审核信任确切的钩子定义。** 官方要求新的或更改后的非托管钩子在信任前跳过；在 Codex CLI 用 `/hooks` 查看和信任，且项目配置层本身需要受信任。不要修改信任数据库或使用绕过信任的参数来声称启用完成。参考 [官方 Hooks 文档](https://learn.chatgpt.com/docs/hooks)。

状态仅保存在项目 `.model-qa/`，报告、看图记录和 Blender 日志保存在各验收单旁。全部属于本机任务资料，不提交到技能发行仓库。钩子只检查已登记的当前会话交付物，不扫描整台电脑；未登记任务、未信任钩子、未支持的工具路径或运行失败都不能当成验收通过。检查失败时应报告原因。

## 已验证范围

2026-11-02 在 Blender 5.2.2 LTS / Windows 以合成管道和支座验证：正常模型通过；尺寸偏差、脱离支座、交叠干涉、端口错位、内腔堵塞、实体完全包容及默认特写分别触发对应失败。检查前后原 `.blend` 内容哈希一致。包级测试还覆盖旧报告失效、会话隔离、中断恢复、有限修复和安装合并。测试直接调用官方事件输入/输出协议；这不等同于用户信任后在真实桌面会话中完成钩子触发验收，也不证明任意复杂设备都能自动验收。每台新电脑应先运行对应合成验收。
