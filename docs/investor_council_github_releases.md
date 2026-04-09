# 投资大师智能团 GitHub Releases 发版流程

## 一句话原则

GitHub Releases 是唯一权威发布源。

公开对外时，默认叙事应始终是：
- 普通用户从 GitHub Releases 下载 `投资大师智能团-Setup.exe`
- `Portable.zip` 是备用路径
- `Codex 一句 prompt` 是高级用户辅助路径

## 1. 本地构建 release

```cmd
BUILD_INVESTOR_COUNCIL_RELEASE.cmd --version v0.1.0
```

构建完成后，正式产物位于：

- `dist/InvestorCouncilReleases/<version>/`

## 2. 每次 release 必须包含的文件

主产物：
- `投资大师智能团-Setup.exe`
- `投资大师智能团-Portable.zip`
- `SHA256SUMS.txt`

法律与说明文档：
- `LICENSE`
- `快速开始-中文.md`
- `发布说明-中文.md`
- `免责声明-风险提示-中文.md`
- `隐私说明-中文.md`
- `使用前提-合规说明-中文.md`
- `Codex一句Prompt自举-中文.md`
- `Codex一句Prompt-复制版.txt`
- `高级用户-Codex一键安装提示词.txt`
- `高级用户-Codex自修复提示词.txt`

发布辅助：
- `release-manifest.json`
- GitHub Releases 页面正文模板

## 3. 发布前检查清单

- 首页不出现内部 prompt、调试信息或乱码
- Livermore 与 Buffett 都能从壳应用发起交接
- 阻塞提示、诊断面板和一键修复可用
- `SHA256SUMS.txt` 只覆盖 `Setup.exe` 与 `Portable.zip`
- release 目录和 `Portable.zip` 内 docs 目录都包含法律与说明文档
- 不要求用户现场安装 Python
- GitHub Releases 文案明确：用户需要自己的 Codex / ChatGPT 权限

## 4. 发布到 GitHub Releases 时的标准口径

发布文案应明确写出：
- 这是一个 Codex 原生产品壳，不是独立大模型
- 用户需要自己的 Codex / ChatGPT 权限
- 首次使用前需要安装并登录 Codex Windows app
- 默认支持 Windows 11 x64
- 默认下载 `Setup.exe`
- `Portable.zip` 和 `Codex 一句 prompt` 仅为备用 / 高级路径
- 产品仅用于教育、研究和信息整理，不构成投资建议
- 产品默认不采集远程遥测，但可能访问公开第三方行情接口

## 5. GitHub Releases 页面正文模板

发布时可直接使用：

- `docs/investor_council_github_release_body_cn.md`

## 6. 内部辅助交付

如需给测试人员或内部支持团队准备更极简的交付包，可以使用“客户交付包”脚本。但这条路径仅限内部辅助，不应作为公开发布主路径，也不应覆盖 GitHub Releases 的版本权威性。
