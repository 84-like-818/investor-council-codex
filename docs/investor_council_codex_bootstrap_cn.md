# 投资大师智能团 Codex 一句 Prompt 自举

这条路径只适合高级用户。

## 使用前提

你需要同时满足以下条件：
- 已安装 Codex Windows app
- 已登录自己的 Codex / ChatGPT 账户
- 已经在 Codex 中打开当前仓库工作区

如果你是纯小白用户，默认仍应走：
- `GitHub Releases -> 投资大师智能团-Setup.exe`

## 直接可用的一句 prompt

```text
请在当前工作区完成“投资大师智能团”的安装和首启：运行 `scripts\bootstrap_investor_council_from_codex.ps1`，自动检查 Codex、同步 skill、创建桌面图标并启动产品；如果 Codex 未安装或未登录，就停在清晰的中文阻塞提示；不要删除仓库外任何非产品文件。
```

## 它会做什么

- 检查 Codex 是否安装
- 检查 Codex 是否登录
- 同步 `investor-council` skill
- 创建桌面图标
- 启动独立壳应用

## 它不能替代什么

它不能替代“把产品文件带到用户机器上”这一步。

也就是说，纯空白机器如果既没有 release 包，也没有源码工作区，仅靠一句 prompt 还不能无中生有地完成整套安装。

## 对外口径

公开对外时，应把这条路径明确标记为：
- 高级用户辅助路径
- 已在 Codex 工作区中的自举路径
- 不是普通用户默认安装入口
