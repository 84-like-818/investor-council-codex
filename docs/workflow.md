# 工作流

## 每次运行做什么

- 读取 manifest
- 检查 URL
- 下载可直接获取的内容
- 保存 HTML 快照
- 提取候选下载链接
- 保存线索
- 扫描本地手工补充资料
- 生成缺失清单和总索引

## 推荐使用方式

### 首次运行

直接跑完整 pipeline。

### 第二轮以后

1. 看 `missing_sources.csv`
2. 处理高优先级但缺失的项目
3. 把手工拿到的文件丢进 `incoming_manual/`
4. 重新跑 pipeline

## 对付“拿不到”的资料

系统会做三件事：

- 保留落地页 HTML
- 保留候选链接
- 在缺失清单里给出下一步动作

## 对付“我已有很多本地资料”

把它们放进：

- `projects/<project>/data/local_library/`
- 或 `projects/<project>/data/incoming_manual/`

下次运行时会自动扫描、算哈希、尝试匹配标题。
