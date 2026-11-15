# 真实 KAI 派生角色工作流

所有步骤继续使用原 assets/<id>/ 数据库、不可覆盖构建／预览目录与执行日志。Godot 是检视目标；.blend、GLB 和组件清单保持独立于游戏。

## 原件与许可

从 [KAI 官方页面](https://sketchfab.com/3d-models/aa56e447b578470b8d6b1b9587fd29ac)正常下载，并取得 [Kenney Mini Dungeon](https://kenney.nl/assets/mini-dungeon)。此处脚本不处理登录，也不通过第三方副本替代原件。

已核验版本：

| 原件 | SHA-256 |
|---|---|
| KAI official ZIP | fc4d52913e4151fb62622f084ea8093c30c1bf09bdf2d4d0fb69f936cd05dd5d |
| KAI source/Warrior Fox.glb | bc7b919637f182f8128d921030c050cb4aab6d34299cabe34fc9658120e0259d |
| Kenney Mini Dungeon 2.0 ZIP | 19c4648680cb1d2e8836cade96cbf9781c0c1f45fbc6d2ce41cee8239a3ec4d8 |
| Kenney colormap.png | bc492d755caf9e64924447f065681be0d5438a33cd0acddc72f3d00fd75893be |

KAI 为 CC-BY-4.0，署名 Realidad Aumentada Empezando Desde Cero；保留许可链接、来源、修改说明，无背书暗示。装备为 Kenney CC0。派生记录组合两者，不把 KAI 改标 CC0。MIT 只覆盖工厂代码。商用、修改、运行时／源文件分发分别记录；third_party_upload 保持 false。

## 从下载 ZIP 完整复现

```powershell
uv sync --locked
uv run --locked python scripts/prepare_v03_records.py --source-zip <official-kai.zip> --equipment-zip <kenney-mini-dungeon.zip>
uv run --locked python tests/e2e_kai.py --source-zip <official-kai.zip> --equipment-zip <kenney-mini-dungeon.zip> --kai-license-record vendor/kai/fc4d52913e41/kai.license.json
```

prepare 命令显式 GET 官方公开元数据和许可文本，验证固定 ZIP 哈希，保存本地证据；不上传模型或调用生成 API。E2E 本身离线运行，要求实际工具已在 PATH 或 BLENDER_BIN/GODOT_BIN/FFMPEG_BIN 配置。其他版本必须先检查许可与内容，再调整明确的样本 profile；不删除哈希检查凑通过。

E2E 每次使用新 ID，保留两个完整原始 ZIP、解包依赖、许可、原 KAI 基线、加工 .blend、加工计划和报告。它调用现有 CLI 完成原件导入／验证、实际 Blender 加工、派生登记／导出、耳尖修改／修订、九动作复用、两套源重建与回滚；原始 stdout/stderr、进程退出码与耗时在 artifacts/kai_e2e/<stamp>/。资产与工具日志留在 assets/。

## 可编辑加工与局部修改

scripts/prepare_kai_sample.py 是真实 Blender 脚本，不是生成服务。examples/kai-authoring.json 配置朝向、面部区域、平滑衰减和真实装备装配。它读取已验证原 KAI editable.blend，保留原八动作曲线、rest rig、权重和 UV 摘要；新增两个非零相对 Shape Keys 和 Face_Expressions，并单独记录顶点选区、最大世界位移、装备原件哈希和材质去重原因。

原导入坐标保留厘米层级，规范化对象负责尺度；加工脚本转至 Godot -Z 前向。原动画导入会优化掉起始静止关键帧，因此构建保留 time=0 前导停留，而不错误地按首个非静止关键帧剪短。原 T-Pose 是显式声明的静止姿势；其他动作仍要求真实骨骼或 Morph 动态。

```powershell
$edit = uv run --locked gaf edit <asset-id> --build <validated-build-id> --operation examples/kai-ear.edit.json | ConvertFrom-Json
uv run --locked gaf revise <asset-id> --source $edit.editable_source --recipe examples/kai-edited.recipe.json --note "Smooth bounded ear-tip edit; preserve rig/face/UV/actions"
```

JSON edit 同时给 Basis 与所有 Shape Keys 应用相同位移，保持相对差分；可配置平滑 falloff。也可人工编辑工作副本后 revise。不要覆盖原 raw、源修订、build 或已失败日志。

Morph 必须在角色配方显式写 `morph_targets=preserve`。GLB 验证稀疏数据、目标和权重通道，Blender 重导入按世界位置及目标差分双向匹配（容差 0.1 mm，允许真实 UV 接缝拆点）。Godot 使用实际 GPU Morph bake，再通过实际 Skin bind 与骨骼变换换算世界位移。不能用目标数量或 API 调用成功代替实际形变证据。

当前按相对 Shape Keys 和最多四个骨影响／顶点验证；共享同一 Morph 数据的多实例需要额外对应，现阶段明确拒绝。两项新增目标只是眉部与口鼻区域改形，不代表完成眨眼、口型或完整面部表情库。

## 同一 Godot Harness 的模式

```powershell
uv run --locked gaf preview <asset-id> --build <validated-build-id> --plugin godot-character --material-mode source --config examples/kai-preview.json --movie
uv run --locked gaf preview <asset-id> --build <validated-build-id> --plugin godot-character --material-mode source --config examples/kai-third-person.json --movie
uv run --locked gaf preview <asset-id> --build <validated-build-id> --plugin godot-character --material-mode source --config examples/kai-performance.json
uv run --locked gaf preview <asset-id> --build <validated-build-id> --plugin godot-character --material-mode source --config examples/kai-interactive.json
```

- inspection：正／背／侧、面部中性与两目标近景；九个实际动作和录像。修改版加 `--animation-source-build <baseline-build-id>`，动作库先保存 .tres 再从磁盘重载，检查骨骼和 Morph 权重对照。
- 修改前后使用同一原供体的动画范围取景，逐张保存实际相机位置、旋转和投影参数；E2E 比较三个视图的镜头参数完全相同。局部修改不会触发自动取景缩放漂移。
- third_person：用 InputMap／Input.parse_input_event 驱动 WASD、两次攻击、剑盾→矛盾→剑盾；记录位移、装备可见网格／世界范围、手持附件相对运动、身体／骨架实例不变。相机跟随平移，不随朝向旋转。
- interactive：相同控制器接受 WASD、空格／鼠标左键、1／2；Esc 或关闭窗口结束并保留记录。交互入口不代表本轮已由人完成手动操作验收。
- performance：关闭供体渲染实例，禁用 vsync，不写电影、不做测量期间 GPU 读回；至少预热 1.2 秒和配置帧数，至少采样 3 秒和配置帧数。报告实际绘制帧数、wall P50/P95/max、Godot process 监视值、draw calls／primitives 和内存。16.667 ms 为本示例 P95 wall 预算，不是通用设备保证或 GPU 专项计时。

## 装备与导出约定

同一 GLB 包含身体与三个真实装备 Mesh，components.json 记录 node、slot、variant、attachment_bone、active_scale／rotation、default_active。所有源变换可逆，备用装备不以零缩放破坏导出。预览在动画求值后按可见性选择槽位，拒绝一个槽同时激活剑和矛。

`gaf export` 同时交付 GLB、components.json 和 notices，包含修订链的 modifications.json，说明后续局部改形。裸 GLB 被其他引擎打开时会包含全部装备；消费端须读取组件清单选择默认装备，不保证任意引擎自动理解此约定。源 .blend、原件和复建配置保留在资产账本，不默认打进运行时包。

跨骨架 retarget、原身体护甲拆分、服装蒙皮、布料和战斗碰撞均不在本轮范围。原 Punch 只是攻击检视动作，握持、穿插、装备风格与面部表情含义仍由人类评审。
