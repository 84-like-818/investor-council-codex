# 投资大师智能团

这版已经切到真正的 `Codex 原生产品` 形态：用户只看见一个总入口 skill，先选人物，再进入对应助手。

## 现在的入口

- 一键入口：[START_INVESTOR_COUNCIL.cmd](E:/livermore-harvest-system/START_INVESTOR_COUNCIL.cmd)
- 兼容安装入口：[INSTALL_CODEX_INVESTOR_COUNCIL.cmd](E:/livermore-harvest-system/INSTALL_CODEX_INVESTOR_COUNCIL.cmd)
- 总入口 skill：[SKILL.md](E:/livermore-harvest-system/codex-skills/investor-council/SKILL.md)
- 导师注册表：[mentor_registry.json](E:/livermore-harvest-system/config/mentor_registry.json)

## 小白怎么用

1. 先安装并登录 Codex 桌面 App。
2. 双击 [START_INVESTOR_COUNCIL.cmd](E:/livermore-harvest-system/START_INVESTOR_COUNCIL.cmd)。
3. 脚本会自动检测 Python 3.11+，缺失时优先尝试在线安装。
4. 脚本会自动复制 skill、创建 `.venv`、安装依赖、建立桌面图标、复制总入口提示词。
5. 脚本会尝试直接拉起 Codex 桌面 App GUI。
6. 进入 Codex 后，直接粘贴剪贴板内容即可进入“投资大师智能团”。

## 当前人物状态

- 已就绪：利弗莫尔
- 已预留结构：巴菲特、芒格、索罗斯、彼得·林奇、达利欧、西蒙斯、格雷厄姆

## 关键边界

- 当前版本仅支持 Windows。
- 当前版本坚持 GUI-only，不回退成 CLI 入口。
- 仓库外只会新增或覆盖本产品自有文件，不会删除仓库外任何内容。
- 各人物记忆完全独立，不共享仓位、持股和历史讨论。