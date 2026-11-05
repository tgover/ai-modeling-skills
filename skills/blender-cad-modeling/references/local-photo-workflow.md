# 纯本地照片参考与 Blender 建模

用户于 2026-11-05 明确选择：只用本地 Blender，不接入 Tripo3D 或其他第三方收费生成平台。维护者的默认建模路径保持本地脚本与原生几何。无需安装 Camera to Blender 的服务依赖、WebSocket 插件、ngrok 或填写任何 API Key。

## 与上游项目的关系

参考项目：[ahujasid/camera-to-blender](https://github.com/ahujasid/camera-to-blender)，核对版本 `dee5daedaa6f9bd8f4453ada860fac7fe71d1585`。它的实际三维生成由 Tripo3D 云端完成，Gemini 可选处理图片，服务把生成的网格送入 Blender。克隆源码、启动网页或连接 Blender 并不提供离线三维生成。

本技能已独立实现本地参考图插件与批处理脚本，并进一步借鉴主体整理、快速预览与完整材质成品分工的思路，形成 [本地建模方法](photo-modeling-method.md)。该方法指导轮廓与比例起步、实体结构深化、材质和固定视角对照；用户要求建模时继续建立实际几何，不停在导入参考图。不分发或调用上游云服务代码，不声称上游完整项目已离线运行或单张照片可自动恢复精确三维。

## 在当前 Blender 安装一次

插件源码位于 `assets/local_photo_reference/__init__.py`，只用 Blender 自带 Python 模块。支持 Blender 4.0+；初次运行验证环境为 Blender 5.2.2 Windows，其他版本需要自检。

关闭正在编辑的 Blender，或先保存当前工作。用已配置的宿主 Python 运行：

```powershell
& '<host-python>' '<skill>/scripts/run_blender.py' --use-preferences --script '<skill>/scripts/install_local_photo_addon.py'
```

安装器复制这个插件并启用，保存当前 Blender 版本的用户首选项，不改启动场景。更新已安装插件时保留一个 `.py.previous` 备份；已有备份需要先检查后再更新。不要将安装器用于覆盖其他来源的同名插件；其他插件与首选项应保持原样。若 Blender 正在运行，保存后重开，使当前会话读取插件。

也可将 `assets/local_photo_reference/` 目录打成 ZIP，从 Blender 的 Preferences → Add-ons → Install from Disk 安装并启用。不要安装上游 `ws_import_addon.zip`。

## 照片进入本地项目

1. 手机或相机拍摄前/后/侧/顶视图、接口和内部细节，通过 USB 或已有文件同步方式存到当前任务的 `references/`。同一对象使用相同型号、修订和状态；已知尺寸或尺标应与待标定表面共面，尽量正对拍摄。
2. 检查图片本身，再在 Blender 三维视图按 `N`，打开“本地参考图”页签。选择参考方向，点击“导入本地参考图”，可多选。图片作为独立 IMAGE Empty 进入 `References | Local Photos` 集合并打包，不创建实体、不删除场景物件，也不改变场景单位。
3. 选中某张参考图。输入两个端点的原图像素坐标和已知距离（毫米），点击标定。像素原点位于图片左上角，X 向右、Y 向下；导入后端点默认跨越整张图宽，只有已知距离确实对应这段跨度时才能使用。图片被裁剪、缩放或旋转后须按当前像素重新取点。
4. 照片使用“照片平面比例估计”；仅真实正交图/扫描图使用“正交图 / 扫描图标定”。标定只设定平面比例，不恢复透视、深度、镜头参数或隐藏结构。未标定图只是显示尺寸，不能当作 1:1。不同视图的尺寸互相核对，冲突单列。
5. 用本地 `bpy`、网格、曲线和修改器建立可编辑实体，尺寸以图纸/实测为准。保留参考集合、参数、来源与未知项；实体细节仍遵从 [设备质量要求](equipment-quality.md)，不能用照片取代柜体、接口或按钮。
6. 可导出参考图与标定记录 JSON，包含文件来源、SHA-256、原图尺寸、比例依据及当前比例有效性。若之后更改图片显示大小、物体缩放或场景单位，重新标定并导出；旧 JSON 是当时快照。保存重开，检查图片仍被打包和参考比例仍正确。实际交付模型继续执行 [交付检查](quality-gate.md)。

插件不拍摄或上传照片，不开启监听端口；使用相机应用采集即可。除 Blender 和现有宿主环境外不增加运行依赖。单张透视照片无法确认背面、内部和实际深度，缺失信息按任务记录，不自动虚构。

## 批量参考图准备

复制 `assets/photo-references.example.json` 到任务目录，改为实际图片路径与原图像素端点。图片路径相对这份 JSON；`location_scene_units` 使用当前 Blender 场景单位，标定的 `known_distance_mm` 始终是毫米。允许省略 `calibration`，此时保持未标定显示。

```powershell
& '<host-python>' '<skill>/scripts/run_blender.py' --script '<skill>/scripts/prepare_photo_references.py' -- --manifest '<task>/photo-references.json' --output '<task>/references-v01.blend' --report '<task>/reference-record.json'
```

延续现有文件时加 `--blend '<latest.blend>'`，导入脚本不会清场。选择新的输出文件与报告路径，已有文件会被拒绝，避免覆盖用户修改。准备参考图并不建立设备几何；先读导入报告，再按主技能建模。

## 验证范围

`tests/blender_photo_reference_fixture.py` 是技能维护用合成测试，分 create/reopen 两次独立 Blender 进程验证：横图/竖图、前/侧方向、两点比例、场景单位、错误输入、保留原物件、网络访问禁用、图片打包和原文件不可访问时重开。它不证明任意照片都可精确还原，也不替代实际设备的建模验收。
