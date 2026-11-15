# v0.3 调查与实施范围

调查日期：2026-11-15。基于公开版 v0.2.0 / `bf874b0`，工作分支 `develop/v0.3`。这是调查检查点，不是 v0.3 发布或端到端验收报告。

用户确认：优先狼／狐等兽头双足角色；没有现成授权模型，继续寻找可免费合法获取的样本。

## 已核查的仓库事实

- 工作目录为当前公开维护仓库。原本地工厂、完整资产历史和原游戏均未修改；没有启动被冻结的生成器。
- 复用 core 的登记／修订／事务／运行记录、现有 CLI、character_worker、GLB 验证器、Godot 角色预览与三个 E2E 驱动，不建立第二套资产数据库或 Harness。
- character_worker 现在明确拒绝任何 shape keys，导出也设置 `export_morph=False`。glb.py 同时拒绝 primitive targets 和 weights 动画通道。不能把取消一处报错称为 Morph 支持。
- 现有局部修改只移动基础网格，没有同步处理 shape keys 的相对差分；带 Morph 的模型需要验证基形和所有目标的修改一致性。
- 角色构建检查动作名称、关节名称、时长和受保护摘要，但尚无多装备语义、完整骨架兼容签名或跨骨架重定向。
- Godot 当前是锁定检视相机、播放全部原动作和重新加载动作库的预览；没有第三人称移动控制、攻击状态、装备槽切换或独立性能采样。现有录像强制定时，不能拿录像 FPS 当性能。
- `scripts/probe_character.py` 已扩展为原件只读调查：保留原 Fox 调用方式，增加显式 source/output，报告实际骨骼、蒙皮、材质槽、动作通道和非零 Morph。它不会生成角色、构建 GLB、批准许可或签发 E2E 回执。

## 原有回归已实际保留并重跑

| 检查 | 本轮实际结果 |
|---|---|
| 原 Python 测试 | 36 passed |
| 原 Fox 角色 E2E | 19 步通过，保留预期失败用例 |
| 原 Lantern PBR E2E | 12 步通过，保留许可拒绝用例 |
| 原 0.1 静态 E2E | 18 步通过；使用最初的 CC0 male_anatomy.blend，没有用 Lantern 替换人体试件 |

完整原始日志留在本地忽略目录 artifacts/v03/baseline、assets 中的运行记录及各 E2E 目录。公开摘要见 [research.json](research.json)。生产代码和版本号仍为 0.2.0，尚未增加已验证的 Morph／装备能力。

## 主样本准入：先取得原文件，再认定能力

候选必须同时具有：完整狼／狐双足外形；可明确区分的服装／装备部件；多个真实网格和材质分配；已有可用骨架、蒙皮和至少行走／攻击动作；至少两个具有实际面部顶点差分的表情目标。必须记录原件、版本、作者、明确权利、原始许可、所有依赖和 SHA-256。

网格、材质、动作、Morph 的数量只是准入线索。还要实际查看完整角色、确认“衣服”不是身体贴图、“装备”不是重复角色实例、面部 Morph 不是身体缩放，并测试变形。缺项不通过改名、拆网格凑数量、空动作、程序化假人或四足 Fox 来补齐。

### 实际调查结果

| 候选 | 权利和可获取性 | 已取得文件的实际结果 | 当前结论 |
|---|---|---|---|
| KAI — The Little Fox Warrior，作者 Realidad Aumentada Empezando Desde Cero | 官方 Sketchfab API 标注 CC-BY 4.0、可下载，8 个动作；正常下载 API 匿名请求返回 401，浏览器导航与恢复均超时 | 尚未取得原件；多 Mesh、多材质、可拆装备、面部 Morph 全部未知 | 最接近动作需求的待核验候选，未批准为主样本 |
| Wolfman，Polygonal Mind / 100Avatars R1 | 作者目录和原 VRM 元数据标 CC0，原文件可直接获取 | 原容器及真实 Blender 导入均为 1 Mesh、1 材质、65 骨、16 个目标（15 个非零）、0 动作 | 可作为后续 Morph 补测件，不符合完整主样本 |
| Buffedwolf，100Avatars R3 | 目录和原 VRM 元数据标 CC0，原件可直接获取 | 1 Mesh、1 材质、60 骨、14 个非零 Morph、0 动作 | 不符合完整主样本 |
| MeganTheFox，100Avatars R3 | 目录和原 VRM 元数据标 CC0，原件可直接获取 | 1 Mesh、1 材质、46 骨、14 个非零 Morph、0 动作 | 不符合完整主样本 |
| trev3d/vrcfox | 实际 LICENSE 是 CC-BY-NC 4.0，不能误认成 CC0 | 仅核查官方仓库／许可，未检查 Blender 原件 | 不能用作默认商业导出的示例；非商业补测也需单独完整核验 |
| 博客同名 wolf.glb 的公开仓库副本 | 下载后的 glTF copyright 指向 Dennis Haupt，而不是 KAI 作者 | 实际含 6 Mesh／6 材质、49 骨、5 动作、无 Morph；与 KAI 身份不一致 | 不套用 KAI 的许可，隔离为身份不符候选，不集成 |

三套 VRM 都已保存原始二进制，并在真实 Blender 5.2.3 下导入检查。Wolfman 的 target_15 没有实际位移，未将它计入有效差分目标；零目标不一定是错误，但不能把命名目标数量等同有效表情数量。没有把“目录写了 VRM”当成骨架／Morph 存在的证据，也没有将它们宣称为已有动画角色。

KAI 的官方身份依据：[官方模型元数据](https://api.sketchfab.com/v3/models/aa56e447b578470b8d6b1b9587fd29ac)。VRM 原始目录、逐件下载 URL 和许可入口见 [Open Source Avatars](https://github.com/ToxSam/open-source-avatars)、[R1](https://github.com/ToxSam/open-source-avatars/blob/main/data/avatars/100avatars-r1.json)、[R3](https://github.com/ToxSam/open-source-avatars/blob/main/data/avatars/100avatars-r3.json)。vrcfox 的实际许可见 [LICENSE](https://github.com/trev3d/vrcfox/blob/5034c09f175b3c75c4a4a190e1f6672f368dfdf6/LICENSE)。固定原件哈希和实际探针结果见 research.json；完整取得记录在本地保留。

## 限定的实施顺序与验收

在主样本通过上述准入后，按以下顺序推进，不预先把七项能力标成完成：

| 顺序 | 扩展现有位置 | 必须取得的真实证据 |
|---|---|---|
| 1. 完整导入／导出 | character_worker、BlenderCharacter、GlbCharacterValidate | 原件→可编辑 .blend→GLB→重新导入；逐 Mesh 比较几何、材质槽／实际分配、蒙皮、骨架父子／静止变换／逆绑定、原动作与外部纹理；不静默合并部件 |
| 2. Morph 保留 | 同一 character_worker、glb.py 与角色校验插件 | 显式保留设置；逐网格目标数量／名称／相对基形／非零差分、weights 通道及采样范围；GLB 和 Blender 重导入一致；Godot 实际显示眨眼／张嘴差异。坏索引、错误目标数量、非法权重通道有拒绝测试 |
| 3. 改造与换装源修订 | 现有 edit／revise／checkout | 局部造型修改不破坏未选顶点、UV、蒙皮和面部相对差分；已有真实服装／装备 A、B 配置形成可回退修订，改变的范围写入操作记录；骨架和动作不因换装替换 |
| 4. 兼容动作库复用 | 现有 animation-source-build、角色预览 | 显式匹配父子关系、关节静止变换和轨道，原动作库保存到磁盘再载入变体；比较关节和实际皮肤运动。名字相同但静止姿态／层级不同必须拒绝，不能只按骨名判断兼容 |
| 5. 第三人称样本检视 | 扩展现有 Godot character_preview 和预览配置，不另建游戏工程 | 同一角色在固定第三人称相机下实际走动、转向、攻击和切换装备；记录动作切换、位移、骨架实例及装备节点状态，保留交互入口和脚本化输入录像；旧固定相机模式仍可回归 |
| 6. 重建／回滚／比较 | 现有 E2E、源修订与运行回执 | 基线／改造版同相机同灯光对比，含全身正背侧、第三人称背影、面部近景和动作短片；从原件及修改源分别复建，记录文件与语义一致性；checkout 后恢复原装备和 Morph。人类负责造型、变形、材质与动作观感验收 |
| 7. 性能 | 同一 Godot 检视器的独立非录像测试模式 | 固定机器／渲染器／分辨率，预热后记录真实帧时分布、draw calls、三角和内存等可用指标；基线与变体对照。强制定时录像不能充当性能记录；预算写入测试配置并明确机器适用范围 |

兼容骨架动作复用不是跨骨架重定向。本轮不承诺通用 retargeter；不兼容源需要另行显式准备、许可和转换记录，不能在复用路径偷偷改骨架。新绑定、自动重拓扑、大规模服装制作、收费生成、Agent 框架、完整游戏和其他游戏 Mod Adapter 均不在本轮范围。

## 当前检查点

**尚无同时满足全部要求且已取得原文件的主样本。** 此时优先解决合法取得和完整内容核验，不用不完整 VRM、单个 Morph 补测或新增元数据冒充 v0.3 端到端完成。不发布 v0.3 标签，不更新“已支持”列表。

后续取得的每个新候选继续使用同一探针和登记系统：

```powershell
& $env:BLENDER_BIN --background --factory-startup --disable-autoexec --python-exit-code 23 --python scripts/probe_character.py -- . --source <模型原件> --output artifacts/v03/source-probes/<新的检查目录>
```

原件不修改；探针拒绝覆盖已有报告。VRM 仅以相同字节的 GLB 扩展名别名交给现有 glTF 导入器，明确不认证 VRM 表情映射、MToon、弹簧骨骼或 VRM 运行时语义。正式 v0.3 支持必须由真实完整角色 E2E 和人类视觉评审分别证明。
