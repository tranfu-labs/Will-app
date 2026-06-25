# yizhi 问题总结 —— 自适应问题求解的缺口

状态:2026-06。目的:把"yizhi 当前太简单"这件事拆成可定位、可对照 GitHub 成熟方案的具体问题清单。配套 [will-engine-production-roadmap.md](will-engine-production-roadmap.md)。

## 核心问题:一种策略打天下

**人类对不同问题有不同解法方案**:看一眼"2+2"直接答;中等题略加推理;高考大题则要立项、一步步算、发现问题、解决问题、循环到完成;大工程还要多人协作分工。

**yizhi 当前:所有问题——不分简单复杂——都过同一个"单动作受治理回路"**(观察→思维→选一个动作→反思→预算)。它**只有一种解题策略**,既不会对简单问题"直接答",也不会对复杂问题"立项攻坚"。这就是"太简单"的根因。

## 问题清单(可对照成熟方案)

| # | 问题 | 现状 | 它阻碍什么 |
|---|---|---|---|
| **P1 无复杂度分诊** | 不会判断"这题一句话能答 vs 要立项的工程" | ❌ 一刀切 | 无法把问题路由到合适策略 |
| **P2 无策略库(repertoire)** | 只有"单动作受治理回路"一种解法 | ❌ | 简单题/复杂题/研究题都同一套,都不贴 |
| **P3 简单问题被过度处理** | 一句话能答的也走全套 observe→recall→drives→intention→gate→budget | ❌ | 浪费、慢、贵 |
| **P4 复杂问题被欠处理** | 难题也只"每步一个动作 + 预分解计划",不够 | 🟡 plan-execute 是种子但浅 | 做不了真复杂工程 |
| **P5 求解不"边做边发现"** | plan 是"预分解→执行→卡住才replan",像菜谱非推导 | 🟡 | 难题的路要靠"做"才能发现,预规划解不出大题 |
| **P6 不会"质疑框架/发现问题本身"** | 有 calibration(我准不准),无"这结论/框架对不对、漏了啥" | 🟡 | funding-diff 假阴性(只测主流币)发现不了;研究的最高价值能力缺失 |
| **P7 无协作/委派** | 单回路,不能派子 agent 分工再整合 | ❌ | 做不了需并行/分工的大项目(如批量回测数百品种) |
| **P8 无工作层级** | 有 action/plan/goal,无 project(完成定义)/campaign/portfolio | 🟡 | "复杂项目"这个层级不存在 |

## 统一成一个元问题

> **yizhi 缺"自适应问题求解":(a) 识别问题是什么类型/多复杂 + (b) 从一个策略库里部署匹配的解法。** 现在它对一切都用同一把锤子。

## 问题的"光谱"与各自需要的策略

| 问题类型 | 例子 | 需要的策略 | yizhi 现状 |
|---|---|---|---|
| **简单/事实** | "ArbBot 用什么数据库" | LLM 直接答(System 1) | ❌ 也走全套回路 |
| **中等/单步推理** | "这个回测 n_entered=0 说明什么" | 简短推理 + 一两个动作 | 🟡 勉强 |
| **复杂/项目** | "找出 funding-diff 在长尾品种的真 edge" | 立项 → 分步推进 → 边做边发现 → 迭代 → 完成定义 | ❌ 只有浅 plan-execute |
| **研究/开放** | "ArbBot 还有哪些没被发现的套利机会" | 假设生成 → 质疑 → 扩大搜索 → 批量验证 → 综合 | ❌ |
| **大工程/协作** | "回测数百品种 × 多策略族" | 分诊 → 委派多 agent 分工 → 整合 | ❌ |

## 候选解法(GitHub 成熟方案调研后,2026-06)

**总纲**:Anthropic《Building Effective Agents》给了全套模式词汇,且**明确是"移植模式"非框架**(正好=ADR-001)。其 building blocks 干净映射到 P1-P8。两条研究硬约束定调:

> **硬约束 ①:别建"策略动物园"。** 运行时在 ToT/GoT/LATS/Reflexion 间元选择是**纯研究、无可生产 repo、高成本**。只建一个小的显式路由器(3-4 个命名策略)。
> **硬约束 ②:LLM 不能靠"内省"自我纠错推理。** Self-Refine/同模型自我怀疑是**净负**(Huang et al. ICLR'24:GPT-4 95.5%→91.5%)。批判**必须接外部 oracle**——而 yizhi **已经有**(自己的 make test/回测探针 + calibration Brier)。这是别人没有的优势。

| # | 问题 | 决策 | 源模式(repo/cite) | 落到 yizhi 的最小改动 |
|---|---|---|---|---|
| **P1** 复杂度分诊 | **移植(基石)** | Adaptive-RAG 三档分类(LLM-as-judge 约束输出),Anthropic Routing | `goals.py` 加 `triage_goal→Strategy∈{DIRECT,SINGLE_ACTION,PLAN_CAMPAIGN,DELEGATE}`,在 goal-genesis 前调;默认=PLAN_CAMPAIGN(今行为,纯增量)。~40 行,发 `GOAL_TRIAGED` 事件 |
| **P2** 策略库 | **调架构(小路由非动物园)** | — | repertoire = P1 路由器的输出分支接到现有代码,不做可插拔策略市场 |
| **P3** 简单直接答 | **移植(随 P1 落地)** | Anthropic "Augmented LLM, no wrapper" | DIRECT 分支凭认知+召回直接答、写记忆,**不进 decompose_goal**,省战役成本 |
| **P4** 复杂深处理 | **调架构(已有,深化)** | Orchestrator-workers | 就是现有 `decompose_goal`+cursor+stall-replan,保留 |
| **P5** 涌现推进 | **已是成熟混合(微升级)** | 粗计划+ReAct 反应步+按需 replan(=SWE-agent/Claude Code 收敛形) | **yizhi 已实现此推荐架构**;唯一升级:stall 时生成"为何卡"的**有据反思**喂 replan,替代现在的简略字符串(~25 行) |
| **P6** 批判/发现 | **移植+调架构(守硬约束②)** | CRITIC(工具接地)+ evaluator-optimizer | 加受治理 `critique` 动作:**对照外部 oracle**(重跑探针/对账本/predicted-vs-actual)质疑刚得结论,发 `CRITIQUE_RAISED`;生成式"找漏/假阴性"=devil's-advocate 扫账本,留作后续实验 |
| **P7** 委派/编排 | **延后(ADR-001 触发器)** | Anthropic orchestrator-worker 契约 + Magentic-One 停滞账本 + 租 Claude Agent SDK 子 agent | 子 agent 继承**同一白名单+闸**;**预算门控、稀有、重读研究**用(多 agent ~15× token);**禁持久子 agent** |
| **P8** 工作层级 | **调架构(延后)** | orchestrator-workers 递归嵌套 | 未来加 `Campaign/Project` schema(挂未建的 Vision 模块);P1+P4 验证单层后再建,勿预建 |

**关键纠正**:yizhi 比想象更接近——**P4/P5 已是成熟形态**(粗计划+反应步+停滞 replan = SWE-agent/Claude Code 收敛架构;停滞账本 = Magentic-One 单 agent 版)。缺的基石是 **P1 分诊路由器**,补上后 P3/P4 自然到位。

**Top 3 最高杠杆**:① P1 分诊路由器(基石,~40 行增量,解锁 P2/P3/P4)② P6 工具接地批判(最高新意,**复用 yizhi 独有的外部 oracle**,正是 funding-diff "发现假阴性"所需)③ P5 stall 反思入 replan(~25 行,replan 从盲目变有据)。

**原则不变**(ADR-001):成熟模式**移植吸收**、基础设施**直接租**、治理核心**自研**、框架运行时**不整吞但留接缝**。

## 多 LLM SDK + 最终可租性裁决(2026-06 二次调研)

**硬约束**:will agent 要给多个 LLM 用 → 不绑 Claude Agent SDK(Claude-only),用 LLM-agnostic 的。

**两个大头直接租(都多 LLM、都是有界接缝、不吞核)**:
- **多 LLM 供应层 = 租 LiteLLM**(BerriAI/litellm,MIT,51k★,100+ 供应商一个 OpenAI 兼容 API)。在现有 `LLMClient` Protocol 下加一个 `LiteLLMClient` 类(Protocol 不变、离线默认不变、懒导入),`provider!=openai → LiteLLMClient`。**一个类,yizhi 立刻支持任意供应商。** 装 base SDK(12 依赖),**不要 `[proxy]` extra**(~30 个 server 包)。
- **多 agent 委派层 = 租 Pydantic AI**(pydantic/pydantic-ai,MIT,18k★)。多 LLM(委派可用不同供应商)、pydantic 原生(配 yizhi 唯一硬依赖)、**库不是运行时**(`agent.run()` 在你写的 tool 里调,yizhi 保留外层 loop)、**ArbBot 已用 `pydantic-ai>=1.100`**(同栈)。`UsageLimits` = 预算钩;`can_afford/spend` 门控 spawn;子 agent 内**重应用双墙**(env 白名单+确定性 verify)。新 `engine/delegation.py` ~60 行作接缝。备选:纯 LiteLLM 后端的 yizhi 原生 delegator(零新 agent 依赖)。

**最终可租性裁决(诚实:只有 ① 部分可租,其余结构性自研)**:

| 缺口 | 裁决 | 项目/模式 | 工作量 | 真能租? |
|---|---|---|---|---|
| **① 分诊** | 部分租 / 移植 | RouteLLM(Apache,5.1k,用 `bert`/`causal_llm` 路由避开 OpenAI 嵌入依赖)给"信号";控制流分支自写 | ~40 行 | 部分(租分数,不租决策) |
| **② 工作记忆** | **无库=schema** | mem0/Letta/Zep/cognee 全是**长期**记忆;**没人卖瞬态草稿纸** | 1 个 pydantic 字段(挂 WillState,完成即清) | 否(本质是数据模型) |
| **③ 涌现推进** | 移植 | reflection-on-stall→改剩余计划(在现有 stall-replan 上加 delta) | ~30-60 行 | 否(都是 LangGraph 内模式) |
| **④ 批判** | 移植(oracle 自有) | CRITIC 循环形;**oracle=yizhi 自己的探针+calibration**;研究证实纯内省净负=**自研路线被验证对** | ~80-120 行胶水 | 否(循环已知,oracle 是你的) |
| **⑤ 委派** | **直接租** | **Pydantic AI**(上文) | ~60 行接缝 | **是** |
| **⑥ 工作层级** | **无库=schema** | HTN(PyHOP)是错范式(符号、手写分解);BabyAGI 已归档 | Project pydantic 模型+DoD+预算分配 | 否(治理 schema) |
| **多 LLM 层** | **直接租** | **LiteLLM**(上文) | ~1 个类 | **是** |

**诚实总结**:大头(多 LLM 供应层、多 agent 委派)**确实直接租**(LiteLLM + Pydantic AI,都多 LLM)。①分诊部分可租。②③④⑥**租不到不是生态缺口,是结构性的**——②⑥ 因 yizhi 事件溯源+pydantic 原生而是 schema;③④ 是治理/oracle 胶水,租任何框架都会破多 LLM 或破治理。**没有一处在"造轮子":要么租库、要么移植模式、要么写 schema 字段。**
