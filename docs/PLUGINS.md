# 本地插件与未来导出配置

核心通过 `importlib.metadata.entry_points(group='game_asset_factory.plugins')` 发现已安装插件，并与内置插件合并；同名注册直接失败。安装扩展是显式的本地代码信任决定，不通过自动下载目录加载未知脚本。

插件类提供 `name`、`action`、`category`、`network`、`upload`、`paid` 和 `run(context)`。action 为 build、validate、preview 或 export 中的一个，CLI 的 `--plugin` 指定名称。类别可以是 3d、2d、ai、animation、preview、export；类别标签本身不产生能力。当前可用插件以 `gaf plugins` 输出为准。

外部包在 pyproject 配置 entry point：

```toml
[project.entry-points."game_asset_factory.plugins"]
my-format = "my_export.plugin:MyExport"
```

run 收到已校验的资产路径、源修订、不可覆盖运行目录、可选构建及记录对象。返回 JSON 可序列化的输出哈希与元数据；异常会记录失败并返回非零。插件应把结果写入 `context.output('exports')` 等新目录；用 core.process 调外部程序以保留命令和日志。

登记核心接收任意单个本地源文件＋sidecar，不限定为 3D。配方公共层只有 schema_version 和 build_plugin；blender-static 的专用字段有额外 schema，其他插件负责验证自己的设置。构建插件必须写入 build.json：id、status=succeeded、revision、revision_sha256、outputs 文件哈希表，并返回 build_id 和 build_manifest_sha256；不要假定 outputs 一定有 model.glb。公共核心只核对通用构建回执与输出哈希，GLB、Blender 和 Godot 的具体假设保留在各自插件内部。可参照 BlenderStatic 的实际实现，不注册空的未来模块。

内置 GLB exporter 读取 `profiles/glb.json`，核对要求的验证器与授权条件，把 profile 哈希写入导出记录；不会依赖 Godot。新 Mod profile 通常是单独的 export 插件＋版本固定的 profile 文件，增加宿主版本、命名／轴向／格式、运行时文件组成、源文件是否可分发等约束。当前没有任何具体游戏 Mod profile，不把只写元数据的模板当成实现。

基础调度器拒绝 network/upload/paid=true。将来扩展 AI 生成时需要独立的授权对象、允许上传的输入哈希和许可、目标供应商／模型版本／任务 ID／费用上限／失败重试边界；也需要保存原始下载，不能把 prompt/seed 当成永远可重建的源文件。当前没有可调用的 AI 生产后端，也没有已实现的生成命令。

插件必须保留 visual_review=pending_human。自动操作可以报告具体文件／画面观察，但不能给资产签发视觉质量通过状态。

## 0.2 增量

新增 blender-character、glb-character、godot-character，以及 action=edit 的 blender-character-edit。仍使用原 Context／运行记录／源修订，不新增 Agent 框架。GLB exporter 根据 character build 自动选择 glb-character profile，并继续独立检查 commercial/noncommercial 与 runtime_distribution；profile 不能绕过商业用途检查。完整操作见 [CHARACTER_WORKFLOW.md](CHARACTER_WORKFLOW.md)。
