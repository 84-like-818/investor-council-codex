# Persona Skill Factory for Codex

这是一套给 **Codex** 用的人物 skill 工厂模板。目标不是只做一个 Livermore，而是把你后续在 Codex 里的研究、讨论、修订，持续沉淀成可复用的 **skill / plugin / 智能团节点**。

## 你会得到什么

- 一套适合人物蒸馏的目录结构
- 一键脚手架脚本：快速生成新人物
- 讨论结果沉淀模板：把后续对话变成 doctrine / voice / anti-pattern / eval
- repo skill + plugin 双形态
- 适合“人物智能团”的长期维护方式

## 建议的总原则

1. **一个人物，不只一个文件。**  
   至少拆成：`role`、`voice`、`doctrine`、`anti-patterns`、`modern-translation`、`evals`。

2. **静态人格和动态市场分开。**  
   不要把“今天的市场观点”写进核心 doctrine。  
   每日/每周市场判断，应写到 dated memo 或单独的 live-market 层。

3. **先做 skill，再做 plugin。**  
   在本地调通前，先用 `.agents/skills/<slug>/`。稳定后再同步到 `plugins/<slug>-assistant/`。

4. **任何人物都必须写“不会做什么”。**  
   这比“会做什么”更重要。

5. **把 Codex 后续讨论，当作增量训练数据，而不是即时记忆。**  
   每次讨论后，做一次 distill：  
   - 新增了什么原则  
   - 修正了什么误解  
   - 哪些回答越来越像  
   - 哪些回答仍然不像

## 快速开始

```bash
python scripts/create_persona_skill.py --slug livermore --display-name "Jesse Livermore" --role "趋势与时机投资助手"
python scripts/sync_skill_to_plugin.py --slug livermore
```

然后把资料填进：

- `.agents/skills/livermore/references/`
- `.agents/skills/livermore/data/raw_sources/`
- `.agents/skills/livermore/data/session_distillates/`

## 目录

- `docs/`：方法论与运行手册
- `prompts/`：可直接粘贴给 Codex 的提示词
- `scripts/`：生成、同步、沉淀脚本
- `templates/`：skill / plugin 模板
- `examples/`：人物配置示例

## 推荐工作流

1. 先建人物骨架  
2. 填原始资料  
3. 在 Codex 里反复讨论  
4. 每轮讨论后做 distill  
5. 用 eval cases 检查“像不像”  
6. 稳定后同步成 plugin


## 多人物智能团
你可以先生成多个单人物 skill，再生成一个 council skill：

```bash
python scripts/create_persona_skill.py --slug livermore --display-name "Jesse Livermore" --role "趋势与时机投资助手"
python scripts/create_persona_skill.py --slug quality-investor --display-name "Quality Investor" --role "商业质量与估值助手"
python scripts/create_persona_skill.py --slug risk-manager --display-name "Risk Manager" --role "风险与仓位助手"
python scripts/create_council_skill.py --slug investment-council --members livermore,quality-investor,risk-manager
```


## 人物母包 × 工作子包
最快的方法不是“每次从零做一个新 skill”，而是：

- 先做 **人物母包**：voice / doctrine / anti-patterns / modern-translation
- 再做 **工作子包**：chat / market-memo / journal-review / source-harvest

示例：
```bash
python scripts/create_persona_skill.py --slug livermore --display-name "Jesse Livermore" --role "趋势与时机投资助手"
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode chat
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode market-memo
python scripts/create_workmode_skill.py --persona-slug livermore --work-mode journal-review
```
