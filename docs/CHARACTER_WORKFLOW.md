# 0.2 角色资产工作流

继续使用原有 CLI、资产修订、构建回执与导出接口。增加三个角色插件和一个局部修改插件；Godot 仍是可选预览目标，源文件与 GLB 不依赖 Godot。

## 静态与角色路线

| 阶段 | 0.1 静态路线（继续保留） | 0.2 角色路线 |
|---|---|---|
| build | blender-static | blender-character |
| validate | glb-static | glb-character |
| preview | godot-generic | godot-character |
| edit | 使用外部可编辑工作副本再 revise | blender-character-edit，或手工编辑工作副本再 revise |
| export | glb，profile=glb | glb，自动 profile=glb-character |

静态插件继续拒绝真实骨骼，不通过丢弃蒙皮来“兼容”。角色 build 需要真正的骨架、皮肤网格和动作；原始动作名称必须保留，导出动作需有实际关节变化，重新导入也必须读回骨骼、蒙皮、材质与全部动作。

当前角色配置验证 Blender 5.2.3、最多四个骨影响／顶点；超过四个明确拒绝。Morph 默认拒绝，0.3 可用 `morph_targets=preserve` 显式保留，完整真实例子见 [v0.3 工作流](v03/WORKFLOW.md)。尚未验证任意约束／驱动／复杂 rig 或跨不同骨架的重定向，不把“保留现有 rig 与动作”称为自动绑定或通用重定向。

## 一个可复现的真实角色例子

使用固定 commit 的 Khronos Fox：模型由 PixelMannen 提供，CC0；tomkranis 的绑定与动画、AsoboStudio/scurest 的 glTF 转换为 CC-BY-4.0。不能只写“Fox=CC0”。许可、署名、来源、准确版本、哈希和修改说明都在 examples/fox.license.json 及实际资产 licenses 中，export 携带 notices。

```powershell
uv run --locked gaf ingest my-fox --source vendor/khronos-fox/8f492390ddc7/Fox.glb --license-record examples/fox.license.json --recipe examples/fox.recipe.json
$base = uv run --locked gaf build my-fox --plugin blender-character | ConvertFrom-Json
uv run --locked gaf validate my-fox --build $base.build_id --plugin glb-character
uv run --locked gaf preview my-fox --build $base.build_id --plugin godot-character --material-mode source --movie
$edit = uv run --locked gaf edit my-fox --build $base.build_id --operation examples/fox-left-ear.edit.json | ConvertFrom-Json
uv run --locked gaf revise my-fox --source $edit.editable_source --recipe examples/fox-edited.recipe.json --note "只抬高左耳尖，保留骨架、权重、UV、材质和动作"
$variant = uv run --locked gaf build my-fox --revision r0002 --plugin blender-character | ConvertFrom-Json
uv run --locked gaf validate my-fox --build $variant.build_id --plugin glb-character
uv run --locked gaf preview my-fox --build $variant.build_id --plugin godot-character --animation-source-build $base.build_id --material-mode source --movie
uv run --locked gaf export my-fox --build $variant.build_id --usage commercial
```

命令脚本应逐项检查退出码；`tests/e2e_character.py` 展示完整运行与日志。构建输出 editable.blend 可以直接在 Blender 人工修改，再使用 revise 登记，不要求所有造型修改都由预设 JSON 操作表达。

## 局部修改与保持不变的证据

JSON edit 操作使用对象、骨骼权重组、三维范围和位移明确选择区域。示例在 Fox 的 1,728 个源顶点中仅移动 15 个耳尖区域顶点；未选择的位置逐项比较，UV、权重、骨架、动作曲线、材质节点和纹理内容分别摘要检查。选区为空或超出 max_fraction 会失败，原 build 不覆盖。编辑记录与 .blend 存入 edits/<run-id>，只有 revise 才形成正式新源修订。

这是一个实际网格修改例子；不宣称完成通用雕刻、服装、自动重拓扑或所有关节的审美验收。

## 动画复用的实际含义

`--animation-source-build` 指向同一资产的另一个已验证角色 build。预览器从该 GLB 读出原 AnimationLibrary，保存成独立 motions_*.tres，再从磁盘重新载入到修改后的角色 AnimationPlayer，检查轨道路径和骨名。分别播放 Run/Walk/Survey，以骨骼角度变化与实际烘焙蒙皮顶点位移验证动作在驱动变形，并比较供体／变体骨姿态误差。

相机在三个动作的真实蒙皮范围预采样后锁定，不绕角色转台。动画视频为 AnimationPlayer 的真实骨骼动作。原始 0.1 转台仅用于静态检视，不是这项验收的证据。

motions_*.tres 是 Godot 专用预览／复用产物；通用可编辑骨骼／动作仍保留在 .blend 与 GLB。对不兼容骨架，轨道解析或姿态对比失败就报告失败，不暗中改骨名或伪造重新绑定。

## 回归与边界

`tests/e2e_character.py` 运行真实原件导入、基线预览／导出、局部修改、源修订、变体预览／导出、原动作复用、两个源修订重建，并测试静态插件拒绝真实 rig、空选区修改失败。`tests/e2e_pbr.py` 另用真实多 Mesh／PBR／纹理样本覆盖静态材质路线。`tests/e2e.py` 继续执行原 0.1 静态回归。

所有阶段保存原始工具日志和失败尝试。view_image 实际查看与视频查看记录另存；technical_status=passed 从不把 visual_review 改为通过。当前无 Agent 视觉批准命令。
