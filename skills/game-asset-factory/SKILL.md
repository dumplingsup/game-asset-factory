---
name: game-asset-factory
description: 为个人游戏与 Mod 获取、登记、加工、验证、预览和导出可复用美术资产时，优先使用本地 Game Asset Factory，保留许可、可编辑源和版本。当前支持静态 3D 的真实 Blender/GLB/Godot 链路；2D、骨骼动画和具体 Mod 格式按能力边界转交现有工具。
---

# Game Asset Factory

工厂仓库在 `<factory-root>`，独立于任何游戏。先读该仓库的 `AGENTS.md`、`README.md`；需要扩展时读 `docs/PLUGINS.md`。素材获取、编辑和导出优先复用工厂，游戏工程只接收合适的派生导出件，除非用户明确要求其他位置。

从任意目录调用必须同时指定 uv project 和工厂数据根，避免写入当前游戏：

```powershell
uv run --project <factory-root> --locked gaf --root <factory-root> plugins
uv run --project <factory-root> --locked gaf --root <factory-root> doctor
```

已实现：本地 .blend/GLB/glTF/OBJ/FBX 登记；Blender 静态导入、规范化与 editable.blend；GLB 结构＋真实重导入验证；Godot 灰模／原材质四视图与可选转台；带来源／notices 的版本化 GLB 导出；源修订 revise/checkout。用 `gaf --help` 和各子命令帮助获取实际参数，build 返回的 build_id 传给 validate、preview、export。

先核对来源、作者、版本、许可原文和商用／修改／运行时／源文件分发权，再用 ingest 保存实际原件与证据。每个资产用自己的许可记录，不能把 examples 的 CC0 身份套给其他模型。没有适当输入上传权和用户服务／费用授权，不把素材发到生成服务；基础版没有上传和付费能力。

修改在工作副本中完成，用 revise 登记新源文件与配方；checkout 回到已有修订。不要覆盖 raw、历史 source、builds、previews、exports 或为了通过测试改写记录。构建日志、手工步骤和生成原始输出要留存；远端生成不能只保留 prompt。

实际查看 Godot 原图，明确灰模与原材质模式、朝向、尺度、裁切、缺材质和文件读取问题。技术成功与美术验收分别报告；所有 visual_review 保持 pending_human，Agent 不宣布视觉质量合格。导出前 validate 必须对同一未变更 build 通过。

当前静态 profile 遇到 rig／animation／morph 会拒绝；2D、像素特效、角色绑定动画与具体 Mod profile 尚未实现，先用现有 pixel-art-studio、pixelfx 或对应专用工作流，保留源文件和许可；需要纳入统一生产时再实现插件，不能伪报工厂已支持。按用户范围完成，不自动扩成整款游戏或重构现有项目。
