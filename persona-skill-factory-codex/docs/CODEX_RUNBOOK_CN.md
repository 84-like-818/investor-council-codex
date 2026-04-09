# CODEX_RUNBOOK_CN.md

## 你在 Codex 里最常做的 5 件事

### 1. 生成新人物骨架
```bash
python scripts/create_persona_skill.py --slug <slug> --display-name "<显示名>" --role "<角色>"
```

### 2. 显式调用 skill
在 Codex 里：
```text
$<slug> 先读取你的 references，再按你的角色回答。
```

### 3. 用后续讨论沉淀新资料
把你认为有价值的一轮讨论，整理为 markdown 文件，放进：
```text
.agents/skills/<slug>/data/session_distillates/
```

### 4. 做 plugin 快照
```bash
python scripts/sync_skill_to_plugin.py --slug <slug>
```

### 5. 多人物协作
建议不要一个 skill 模拟所有人物。
而是：
- 每个人物一个 skill
- 再加一个 council skill 负责调度

## 推荐的多人物结构

- `livermore`：趋势 / 时机 / 仓位
- `quality-investor`：商业质量 / 护城河 / 资本配置
- `macro-observer`：流动性 / 宏观节奏 / 政策扰动
- `risk-manager`：仓位上限 / 回撤 / 相关性 / 失效条件
- `council-orchestrator`：把不同人物的观点做成一个讨论面板


## 生成 council skill
```bash
python scripts/create_council_skill.py --slug investment-council --members livermore,quality-investor,risk-manager
```

然后在 Codex 里直接显式调用：
```text
$investment-council 先分别读取成员 skill，再给我共识与分歧。
```


## 生成人物工作子包
```bash
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode chat
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode market-memo
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode journal-review
```
