# ADR 001 — Build vs Rent vs Port: yizhi 的技术架构边界

状态:Accepted(2026-06)。背景:在补"持续运行 / plan-and-execute / 持续思考"三轴前,先定清"哪些自研、哪些直接用成熟项目、哪些参考移植",避免两个极端——以"治理"之名手搓通用管道(换皮重造),或整吞框架把治理核心交出去(被俘获)。

## 当前架构(~3800 行,核心依赖仅 pydantic,零 agent 框架)

```
core   (383)  领域类型(WillState/MemoryRecord/Plan/Budget)         词汇表
state  (214)  事件溯源:SQLite 事件库 + 快照 + 迁移                持久化(管道)
memory (997)  记忆经济:salience/decay/consolidation/取代/嵌入/排序  ┐ 差异化 70%
engine (1643) 意志回路 run_step + 认知(thought…goals/calibration)  ┘
environments(314) 动作环境(arbbot/self_repo,双墙安全)
eval   (221)  能力 scorecard
```

不变量:**默认确定性、离线、可复现**;每个内在变化都有**语义事件**(MEMORY_SUPERSEDED / BUDGET_HALTED / CALIBRATION_SCORED)。

## 决策原则:边界按「层」划,不按「是否需要意志」划

"意志/治理"作用于**认知**,不作用于**管道**。管道本可租;差异化的认知经济无现成轮子,必须自研。

| 层 | 决策 | 用什么 | 理由 |
|---|---|---|---|
| 受治理认知经济(记忆治理/预算-stake/策略/calibration) | **自研** | — | 生态里没有这件;是护城河与论文级贡献 |
| 领域事件库(语义审计) | **自研** | sqlite(stdlib) | LangGraph checkpointer 是不透明 state blob,非语义审计 |
| 基础设施原语 | **直接租(pip)** | openai·fastembed(已用)·networkx(PageRank)·tenacity(重试) | 该租就租 |
| 被验证的模式 | **移植/吸收** | OpenHands(卡死)·LangGraph(plan+cursor)·Magentic-One(停滞预算)·Generative Agents(显著性反思触发)·A-Mem(联想) | 读源码搬逻辑=吸收轮子,非重推 |
| 控制流运行时(线性回路+薄 runner) | **暂自研(接缝化)** | 一个 while + 移植的 stuck-detector | ~350 行、更轻、保确定性/语义事件;留接缝 |
| agent 全家桶运行时(LangGraph/CrewAI/AutoGen/Letta) | **不整吞** | — | 会替换小而合身、与治理长在一起的管道,得不偿失 |

## 为什么现在不用 LangGraph 当底座

- 它能替换的只是 state 层 + loop 驱动(~8–18%);帮不上差异化的 70%。
- 代价:大依赖树、打破零框架/离线确定性、语义事件日志丢失或重复。
- **阻抗失配**:yizhi 每个状态转移都是受治理的(烧预算/过策略闸/编码 salience/发领域事件),塞进通用 node 等于在每条边上跟框架抽象搏斗;且"一步一 governed run_step + 快照"与"一次 invoke 把图跑完"是两种模型。
- 现回路是**线性**的,LangGraph 的价值在**复杂图**。

**重估触发条件**:当控制流真的变成图——manager 派生并行子 agent、动态多分支编排、需 HITL 审批门/时间旅行调试。届时 LangGraph(或子 agent 用 Claude Agent SDK)值回票价。因此:**runner/plan 设计成可替换接缝,换底座时不动认知核。**

## 落到三轴

1. 持续运行:`engine/runner.py` 的 `run_until` 薄 while 包 `run_step`,移植 OpenHands 卡死检测 + SWE-agent 有界 while + 有界重试。**0 新框架依赖。**
2. plan-and-execute:Plan 进 WillState + 跨循环 cursor(LangGraph 形)、停滞预算 replan(Magentic-One,用 yizhi 客观信号驱动)。
3. 持续思考/联想:双闸默认模式反思(Generative Agents 显著性 + 预算闸)、两段式联想(A-Mem 嵌入提名→LLM 裁定 + SYNAPSE 护栏)。

清理:删未用的 `mem0ai` 可选依赖(本地嵌入已达成语义召回)。

## 后果

- 既不重复造轮子(模式移植)、又不被框架俘获(治理核自研)。
- 保持轻依赖、离线确定性、语义审计三大不变量。
- 留好换底座接缝,把"是否上 LangGraph"推迟到证据出现(控制流真复杂)时再决定,而非现在押注。

## 具体库决策(2026-06,二次调研后落定)

按上述原则,落到具体库:

| 用途 | 决定 | 性质 | 边界 |
|---|---|---|---|
| 多 LLM 供应层 | **租 LiteLLM** | 直接租(基础设施) | 现有 `LLMClient` Protocol 下加 `LiteLLMClient` 类;Protocol/双墙/离线默认不变;装 base SDK 不要 `[proxy]` extra |
| 多 agent 委派 | **租 Pydantic AI** | 直接租(有界接缝) | 多 LLM、pydantic 原生、库非运行时、与 ArbBot 同栈;`engine/delegation.py` 接缝,预算门控 spawn + 子 agent 内重应用双墙 |
| 项目知识库 | **租 mem0** | 直接租(基础设施) | 作**独立项目 KB**(ArbBot 持续知识),与 yizhi 自研意志记忆经济**分开**;mem0 不治理意志 |
| 复杂度分诊① | **移植 ~40 行**(可选 RouteLLM 信号) | 移植模式 | 控制流分支自写,留在确定性层 |
| 涌现 replan③ | **移植 ~40 行** | 移植模式 | LangGraph 暂不引入;若引入走"审议/执行分层"缝 |
| 批判④ | **移植 CRITIC 形 + 异 LLM critic** | 移植模式 + 多 LLM | oracle=yizhi 自己探针;LLM 提疑、确定性探针定真伪 |

**框架运行时仍不整吞**(LangGraph/CrewAI/AutoGen 当底座会接管受治理控制平面)。统一缝:**租库/移植在"审议/检索/委派"低治理层,自研守"执行/预算/双墙"高治理核。**
