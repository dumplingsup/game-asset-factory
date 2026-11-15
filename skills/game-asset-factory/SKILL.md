---
name: game-asset-factory
description: 为个人游戏与 Mod 获取、登记、加工、修改、验证、预览和导出美术资产时，优先使用本地 Game Asset Factory。支持静态 PBR 多 Mesh 及保留骨架蒙皮动画的角色工作流、局部修改与兼容 rig 动作复用；保留许可、源文件和版本。
---

# Game Asset Factory

工厂仓库在 `<factory-root>`，独立于任何游戏。先读该仓库的 `AGENTS.md`、`README.md`；需要扩展时读 `docs/PLUGINS.md`。素材获取、编辑和导出优先复用工厂，游戏工程只接收合适的派生导出件，除非用户明确要求其他位置。

从任意目录调用必须同时指定 uv project 和工厂数据根，避免写入当前游戏：

```powershell
uv run --project <factory-root> --locked gaf --root <factory-root> plugins
uv run --project <factory-root> --locked gaf --root <factory-root> doctor
```

已实现：本地原件登记；静态 PBR 多 Mesh 的 Blender／GLB／Godot 链路；角色骨架／蒙皮／材质／动作保留、可编辑 .blend、局部网格修改、真实骨骼动画预览、兼容骨架动作库复用；带 notices 的版本化 GLB 导出与源修订 revise/checkout。用 `gaf --help` 获取实际参数，build 返回的 build_id 传给 validate、preview、export。

静态路线继续使用 blender-static / glb-static / godot-generic；角色路线必须选择 blender-character / glb-character / godot-character，不能把骨骼传给静态插件让其丢弃。角色命令、配方及 edit 示例见仓库 docs/CHARACTER_WORKFLOW.md。--animation-source-build 使用另一个已验证 build 的动作库，真实保存并重载库后在变体上播放；不等于任意骨架重定向。

先核对来源、作者、版本、许可原文和商用／修改／运行时／源文件分发权，再用 ingest 保存实际原件与证据。每个资产用自己的许可记录，不能把 examples 的 CC0 身份套给其他模型；Fox 的模型与 rig/动作有不同许可。默认商业导出同时要求商业权与运行时分发权，非商业用途需显式 --usage noncommercial，仍不能绕过分发许可。没有适当输入上传权和用户服务／费用授权，不把素材发到生成服务；基础版没有上传和付费能力。

修改在工作副本中完成，用 revise 登记新源文件与配方；checkout 回到已有修订。不要覆盖 raw、历史 source、builds、previews、exports 或为了通过测试改写记录。构建日志、手工步骤和生成原始输出要留存；远端生成不能只保留 prompt。

实际查看 Godot 原图，明确灰模与原材质模式、朝向、尺度、裁切、缺材质和文件读取问题。技术成功与美术验收分别报告；所有 visual_review 保持 pending_human，Agent 不宣布视觉质量合格。导出前 validate 必须对同一未变更 build 通过。

当前角色 profile 验证最多四个骨影响／顶点，拒绝 morph 和超过该范围的权重以免静默丢失；自动绑定、任意 retarget、2D 生产和具体 Mod profile 未实现。2D、像素特效继续使用 pixel-art-studio、pixelfx 或对应专用工作流。按用户范围完成，不自动扩成整款游戏或重构现有项目。
