# INVESTOR_COUNCIL_WORKFLOW_CN.md

## 目标

把 `persona-skill-factory-codex` 变成「投资大师智能团」扩人的标准工作流。

每新增一个人物，最终至少要落地成 5 个结果：

1. 一份可复用的人物资料搜集框架
2. 一份蒸馏后的人物包
3. 一份可执行的评测清单
4. 一组 `investor-council` 运行时文件
5. 一次接入验证

## 一、先定边界，不先写口吻

先回答 3 个问题：

1. 这个人物在智能团里负责什么？
2. 他最擅长解决什么问题？
3. 他明确不负责什么？

对投资人物，建议把边界写得比“风格”更硬。

例子：

- 利弗莫尔：负责趋势、时机、仓位纪律、盘面确认；不负责估值、护城河、长期企业质量判断。
- 巴菲特：负责企业质量、护城河、资本配置、估值纪律、长期持有逻辑；不负责短线择时、题材追涨、盘口节奏判断。

## 二、资料搜集按 4 层拆

不要一上来把所有材料混成一锅。按这 4 层收：

### 1. 原始资料

优先级最高。尽量先收这个人物亲自说过、写过、长期重复过的内容。

投资人物常见原始资料：

- 股东信
- 年会问答
- 访谈
- 演讲
- 书籍原文
- 备忘录
- 合伙人信

### 2. 二手研究

只用来帮助整理结构，不拿来替代原始思想。

- 传记
- 研究文章
- 长篇人物解析
- 历史背景说明

### 3. 现代转译

把历史语境翻译成今天可执行的工作语言。

例子：

- “护城河”翻成：定价权、成本优势、网络效应、切换成本、品牌、分销效率
- “安全边际”翻成：经营质量 + 资产负债表 + 买入价格共同形成的下行保护
- “不做不懂的事”翻成：业务模型、盈利结构、竞争格局说不清，就不应重仓

### 4. 你和 Codex 的后续对话沉淀

每次真实使用后，把有价值的对话沉淀成：

- 新增原则
- 新增反模式
- 新增现代转译
- 新增测试问题
- 新增“更像本人”的表达方式

这部分是后续最值钱的增量语料，但必须先筛选再入包，不能原样回灌。

## 三、先做人物包，再做产品包

### 人物包最少要有 7 块

对应工厂文档里的标准：

1. `角色边界`
2. `声音与风格`
3. `Doctrine`
4. `Anti-patterns`
5. `Modern translation`
6. `Evals`
7. `Update log`

如果材料丰富，再补：

- `source-ledger.md`
- `timeline.md`
- `quote-bank.md`
- `biography.md`

### ready 人物还要补一个「本人资料底座」

如果只有 `profile.json + persona.md + answer-contract.md`，那它只能说是「能用的人物包」，还不是「基于本人资料的人物包」。
对 ready 人物，建议至少再补：

- `references/00-read-first.md`
- `references/03-doctrine.md`
- `references/07-source-ledger.md`
- `references/08-update-log.md`

最好再配上至少 3 份可追溯的本人一级资料。

### 运行时产品包最少要有 4 个文件

接入 `investor-council` 时，最少要落成：

- `profile.json`
- `persona.md`
- `answer-contract.md`
- `avatar.svg`

映射关系建议这样做：

- `profile.json`：卡片展示、人物摘要、风格摘要、预览文案、状态
- `persona.md`：角色边界、声音、核心原则、反模式
- `answer-contract.md`：回答结构、优先顺序、固定输出格式、限制
- `avatar.svg`：人物识别与产品感

## 四、推荐的落库顺序

### 第 1 步：建立人物定义

在工厂里先写一份人物定义草案，至少说明：

- `slug`
- `display_name`
- `role`
- `description`
- `default_prompt`

可以参考：

- `examples/personas/livermore.example.yaml`
- `examples/personas/buffett.example.yaml`

### 第 2 步：整理人物资料

先把搜集到的资料按前面的 4 层整理成工作草案，再写成 packet。

### 第 3 步：写运行时人物包

把 packet 压缩进：

- `codex-skills/investor-council/mentors/<slug>/profile.json`
- `codex-skills/investor-council/mentors/<slug>/persona.md`
- `codex-skills/investor-council/mentors/<slug>/answer-contract.md`
- `codex-skills/investor-council/mentors/<slug>/avatar.svg`

### 第 4 步：更新导师注册表

以 `config/mentor_registry.json` 为产品侧主注册表，更新：

- `id`
- `display_name_zh`
- `display_name_en`
- `aliases`
- `status`
- `selection_label`
- `mentor_pack_path`
- `avatar`
- `memory_namespace`

然后运行：

```powershell
.\.venv\Scripts\python.exe .\scripts\sync_investor_council_registry.py
```

把它同步到：

- `codex-skills/investor-council/assets/mentor_registry.json`

### 第 5 步：做最小验证

至少过这 4 个检查：

```powershell
.\.venv\Scripts\python.exe .\codex-skills\investor-council\scripts\mentor_router.py list --format markdown
.\.venv\Scripts\python.exe .\codex-skills\investor-council\scripts\mentor_router.py show --mentor-id buffett --format markdown
.\.venv\Scripts\python.exe -m py_compile .\codex-skills\investor-council\scripts\mentor_router.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_investor_council.ps1 -InstallOnly -SkipGuiLaunch -AllowNotLoggedIn
```

### 第 6 步：开始真实对话，再做 distill

每次和人物聊完以后，把值得保留的内容重新归档到 packet，而不是只留在聊天窗口里。

## 五、推荐的评测框架

每轮至少测 4 类：

1. `像不像这个人`
2. `会不会越界`
3. `会不会把长期原则和短期盘面混掉`
4. `会不会给出可执行帮助`

对投资人物，建议每个问题都至少看这 5 个维度：

- 有没有先给结论
- 有没有明确证据或判断支点
- 有没有行动条件
- 有没有失效条件
- 有没有保留人物自己的风格，而不是变成普通泛化助手

## 六、巴菲特接入时的最小搜集清单

这份清单是给后续继续补强用的：

- 伯克希尔股东信
- 伯克希尔年会问答
- 巴菲特访谈与演讲
- 与芒格同框的问答材料
- 重要投资案例复盘
- 能体现其长期重复原则的二手整理材料

优先抽取的不是“名言”，而是这几类高频判断：

- 什么样的生意值得长期持有
- 什么叫护城河
- 为什么管理层和资本配置重要
- 为什么价格与价值必须一起看
- 什么情况下宁可不做

## 七、接入智能团时的产品要求

新增人物进入 `ready` 前，至少要满足：

1. 壳应用首页可以正常显示人物卡片
2. 该人物有自己的线程名与独立记忆命名空间
3. 该人物回答结构和其他人物有清晰差异
4. 该人物不会越界去回答自己并不擅长的问题
5. 该人物能在当前中国用户语境下被理解和使用

## 八、后续扩人建议

建议按这条顺序扩：

1. 巴菲特：企业质量 / 护城河 / 资本配置
2. 芒格：多元思维模型 / 误判清单 / 反向思考
3. 格雷厄姆：安全边际 / 防守框架 / 估值底线
4. 彼得·林奇：成长线索 / 调研视角 / 分类框架
5. 达利欧：宏观周期 / 组合配置 / 风险平衡
6. 索罗斯：反身性 / 宏观时机 / 叙事与市场互动
7. 西蒙斯：数据 / 因子 / 统计规律

## 2026-04 Researcher-base rule

For a `ready` mentor, the minimum research base is no longer only a profile, persona, and a few notes. The minimum evidence layer is now:
- `source-ledger`
- `primary-source-notes`
- `yearly digest`
- `meeting transcript index`
- `case source anchors`
- `mistake dossiers`
- `clip anchors`
- `paragraph anchors`

Workflow rule:
- build the evidence layer first
- compress the evidence layer into persona and answer behavior second
- only then promote the mentor to `ready`

For future mentors, collect at least three kinds of reusable material:
- yearly primary-source digest
- interview / Q&A / meeting retrieval index
- case map or mistake map


## 2026-04 Mediated-trader rule

For historical market operators such as Livermore, the evidence base is often mediated rather than official. In those cases, a `ready` mentor should still have a real evidence layer, but the structure may differ from a Buffett-style letter archive.

Minimum trader-style evidence layer:
- identity anchors
- direct-attribution work anchors
- strongest clean public proxy text
- episode index
- case maps
- mistake dossiers
- paragraph anchors

Rule: say clearly what is direct, what is proxy, what is contemporary journalism, and what is derived compression.
