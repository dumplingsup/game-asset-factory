# Game Asset Factory

个人游戏与 Mod 的素材生产、加工和交付。资产生产与使用资产的游戏分开管理。

## Language

**Asset / 资产**:
具有稳定身份、来源与许可记录的一份素材及其历代派生件。
_Avoid_: 当前导出文件

**Source revision / 源文件修订**:
一次固定的可编辑素材与加工配方组合；后续修改形成新的修订。
_Avoid_: 最近导出、临时缓存

**Build / 构建**:
从指定源文件修订产生的一次加工结果，可成功或失败。
_Avoid_: 视觉验收

**Export profile / 导出配置**:
面向一种交付用途的格式、文件组成与授权条件约定。
_Avoid_: 游戏项目

**Technical validation / 技术验证**:
对文件结构、完整性和工具可读取性的检查结果。
_Avoid_: 美术合格

**Visual review / 视觉评审**:
人根据实际预览与使用目标作出的美术判断。
_Avoid_: 自动通过
