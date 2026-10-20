# 从图纸到原生 SolidWorks 模型

## 任务划分

读图先确定零件边界、视图方向、单位、基准、剖面、重复关系和加工/装配意图。对有冲突的尺寸列出来源；照片透视和像素比例不能覆盖标注尺寸。只有图片时需要至少一个已知尺寸，未给出的背面、壁厚或连接结构应注明。

常见顺序是主轮廓 → 主体拉伸/旋转 → 切除/开孔 → 筋和凸台 → 阵列 → 圆角/倒角。轴对称件优先旋转，板金件保留钣金与展开信息，装配体分别建立零件并添加配合。根据实际形状调整顺序；复杂曲面分阶段处理，先验证关键截面。

## API 与文件细节

- API 几何以米、弧度表达；用户尺寸先统一单位再转换。STEP/STL/图纸显示单位分别验收。
- 中英文 SW 模板名称不同。按类型遍历基准特征或记录实际名称，不默认字符串 `Front Plane` 一定存在。
- 检查新建文档、草图实体、特征创建的返回值；重建失败即停止。保存前清空选择，防止只导出选中的面或实体。
- 输出到新的、由当前任务指定的路径，保存前检查文件存在性。不要以自动保存方式覆盖用户原模型。
- 给真实设计添加尺寸和关系；样例只有坐标不意味着完成了完全约束。原生草图/特征树、全参数化和制造可交付是不同验收要求。
- `.bas` 是可检查源代码；`.swp` 是保存后的 VBA 项目。不能靠更改后缀转换。
- `RunMacro2` 的返回值和错误码只表示调用情况。宏内部应另行报告几何、重建、保存和导出结果。
- 本包对简单零件保留兼容旧版本的 `IModelDocExtension.SaveAs` 示例。它在 2022 文档中已标记为旧接口；复杂装配复制或带外部引用的保存需按目标版本改用相应新接口，不能照搬简单零件示例。

## 失败与交付

保留最先失败的 API、参数、软件版本和输出。先修复该失败再继续，避免在空实体或错误选集上叠加后续操作。连接异常时先确认注册、打开状态、模态对话框、用户与权限；不默认需要 MCP。

验收覆盖关键尺寸、孔/槽数量与位置、壁厚、实体数、重建、外部引用、保存重开和交换格式重导入。交付说明应区分“只生成了宏”“宏已运行”“模型与导出已验收”。若软件不可用，交付源代码和下一步运行说明，并明确原生模型尚未生成。

## 官方 API 参考

以目标软件内置/API 帮助为准。以下文档用于核对接口含义和参数，不代表已完成对应版本实机验收：

- [2022 API 成员索引](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks_members.html)
- [FeatureExtrusion3 参数及单位](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featureextrusion3.html)
- [RunMacro2 参数与错误码](https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~RunMacro2.html)
- [2022 SaveAs 行为和限制](https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SaveAs.html)
