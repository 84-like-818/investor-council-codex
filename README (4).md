# Livermore 自动化全面采集资料系统

这是一套**清单驱动、可复跑、可追踪、可长期复用**的资料采集系统，核心目标：

1. **尽可能多拿资料**：能直接下载就直接下载。
2. **拿不到也保留线索**：至少保留落地页、候选下载链接、来源信息和错误原因。
3. **自动生成缺失清单**：每次运行后自动产出缺失报告、线索队列和总索引。
4. **可长期复用**：不仅能采 Jesse Livermore，也能扩展到任何人物、主题、项目。

## 这套系统会输出什么

- `projects/<project>/data/acquired/`：真正拿到的文件
- `projects/<project>/data/landing_pages/`：页面快照、候选链接线索
- `projects/<project>/data/incoming_manual/`：你手工补进去的文件投递区
- `projects/<project>/data/local_library/`：你原本就有的本地库
- `projects/<project>/state/acquisition.db`：SQLite 状态数据库
- `projects/<project>/reports/master_index.csv`：总索引
- `projects/<project>/reports/missing_sources.csv`：缺失清单
- `projects/<project>/reports/lead_queue.csv`：线索清单
- `projects/<project>/reports/holdings_catalog.csv`：已获取文件目录
- `projects/<project>/reports/unmatched_local_files.csv`：本地文件但未匹配来源
- `projects/<project>/reports/dashboard.md`：适合人看的摘要

## 支持的采集策略

- 直接文件下载：PDF / EPUB / TXT / ZIP / 图片等
- HTML 正文保存：页面本身就是正文时，直接存为 HTML 内容
- 落地页保留：拿不到正文，也保留页面和候选链接
- 自动提取候选下载链接：例如 PDF、Plain text、EPUB、MOBI、ZIP、Image
- 本地资料合并：扫描你已有文件并自动参与缺失判断
- 多次复跑：系统记录历史，不会每次都从头失忆

## 一键运行

### Windows

双击根目录的 `RUN_WINDOWS.cmd`

### macOS / Linux

```bash
bash run.sh
```

## 手工运行

```bash
python -m venv .venv
. .venv/bin/activate  # Windows 改用 .venv\Scripts\activate
pip install -r requirements.txt
python scripts/pipeline.py --project livermore
```

## 复用到其他主题

```bash
python scripts/create_project.py --project bernard-baruch
python scripts/pipeline.py --project bernard-baruch
```

新项目清单文件在：

```text
projects/bernard-baruch/manifests/seeds_master.csv
```

## Livermore 预置来源

仓库已经预置了一批 Livermore 相关来源，包括：

- Project Gutenberg 的 *Reminiscences of a Stock Operator*
- Open Library 的 *How to Trade in Stocks* 各版页
- Open Library / Internet Archive 的 *Studies in Tape Reading*
- Wikimedia Commons 的 Jesse Livermore 图片页
- TIME 的历史文章入口
- Library of Congress / Chronicling America 的相关页
- Google Books 的多个书目和预览页

## 重要说明

- 请遵守目标网站的使用条款、版权和 robots 规则。
- 对需要登录、借阅、付费、人工验证的网站，系统会尽量保留线索，但不会绕过权限控制。
- 这套系统不是“盗链器”，而是“研究资料采集与证据保留系统”。
