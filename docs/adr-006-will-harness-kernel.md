# ADR-006 — Autonomous Campaign Harness

状态:Accepted(2026-07-06);当前代码、文档和测试已按七模块内核收敛。

一句话: **不要再建设一个全能 Will Agent;建设一个 Autonomous Campaign Harness。**

Will 的存在理由不是替代 pi、Codex、OpenClaw、OpenAI Agents SDK 或 LangGraph。成熟生态已经覆盖了大量工具调用、coding workbench、agent session、handoff、tracing、human-in-loop、channel 和插件能力。Will 只保留那些外部 harness 不会天然拥有的项目语义:

- 一个模糊复杂目标如何升级成 campaign;
- 每个 stage 需要什么 artifact;
- 什么 evidence / schema / validation 算通过;
- worker 和 Soul 的输出如何被采纳、拒绝、返工、入账;
- 最终 delivery pack 如何形成、引用哪些 accepted artifacts、保留哪些限制。

因此,Will 的新工程定义是:

> **Will 是面向复杂目标的 Autonomous Campaign Harness。它负责 campaign contract、controller tick、autonomy boundary、artifact acceptance、worker adapter、SoulLens adoption、ledger、replan/react 和 final delivery。它不负责通用工具执行、coding agent session、browser/search runtime、多渠道壳或 SoulDB。**

## 决策

把 Will 从"Will Agent runtime"收敛为 **Autonomous Campaign Harness**。

推荐分工:

```text
Soul = 方法论 / 世界观 / 工程标准 / 风险批判 lens
pi / Codex = 执行身体:搜索、repo、patch、test、browser、脚本
OpenClaw = 入口 / 多渠道 / 插件 / 审批 UI / session 壳
OpenAI Agents SDK = agent loop / tools / handoff / sessions / tracing 的可选 worker runtime
LangGraph = 未来复杂 workflow / checkpoint / HITL 图编排
Will = Autonomous Campaign Harness
```

Will 保留 L4/L5 层;L0-L2 默认外包;L3 先用当前薄 loop/state machine,待复杂度证明后再迁移。

| 层级 | 名字 | 负责什么 | 推荐归属 |
|---|---|---|---|
| L0 | Tool Harness | shell、browser、search、repo read、patch、test、WebFetch | pi / Codex / OpenClaw tools |
| L1 | Execution Harness | 单个任务内部 plan、tool call、retry、summarize | pi / Codex / OpenAI Agents SDK |
| L2 | Session Harness | thread resume、compaction、channel、approval UI、plugin enablement | OpenClaw / Codex app-server |
| L3 | Workflow Harness | 多步骤任务、handoff、interrupt、checkpoint | 当前薄自研;以后 LangGraph / OpenAI Agents SDK |
| L4 | Campaign Harness | stage cursor、artifact contract、accept/reject、revisit、S1-S5 | Will |
| L5 | Governance Harness | policy、run limits、delivery ledger、adoption record | Will |

## 七模块 Will 核

Will 当前核心只包含七个一等模块:

```text
will/
  campaigns/    CampaignTemplate, Campaign, Stage, ArtifactContract, AcceptanceGate
  controller/   tick phases, route effects, checkpoint/finalization seam
  autonomy/     AutonomyEnvelope, EnvelopeUsage, InterruptionPolicy, StageDecision, gates
  workers/      WorkerAdapter direction, delegation, fake worker, patch drafting
  lenses/       SoulLens protocol, FakeSoulLens, future Soul API lens
  ledger/       append-only events, snapshots, projections
  artifacts/    ArtifactRef, EvidenceRef, DataRef, BacktestRef, DeliveryPack
```

Will can be a Python library + CLI + API called by OpenClaw, pi, Codex, or LangGraph. It does not need to own every agent session.

## Planner / React / Replan 边界

"planner、loop、react、replan"必须分层,不能一刀切。

| 层级 | planner/react/replan 归属 | 说明 |
|---|---|---|
| 工具级 | pi / Codex / OpenAI Agents SDK | 怎么搜索、怎么读文件、怎么跑测试 |
| session 级 | OpenAI Agents SDK / Codex / pi | 一次 agent run 内怎么继续 tool loop |
| workflow 级 | LangGraph later | 有条件分支、interrupt、checkpoint 时 |
| campaign 级 | Will | 哪个 stage 该返工,什么算交付通过 |
| 方法论级 | Soul | 从 LinBiao/Buffett/Musk 等 lens 判断方向是否错了 |

BTC 例子:

```text
pi replan:
  找不到 yfinance 数据,换 CoinGecko/Binance/Kaggle。

Soul replan:
  研究计划缺少一线事实路径,建议回到 S1 修计划。

Will replan:
  采纳 Soul 建议,revisit S1;或拒绝建议继续 S4;或暂停 ask human。
```

Will 不决定低层 HTTP 参数怎么拼。Will 决定"这个 stage 是否足以进入下一 stage"。

## 预算与账本术语

保留预算和账本功能,但降低哲学词汇在 MVP 主路径中的权重。

### ExecutionBudget / RunLimits / CampaignQuota

外显语义:

> 预算是 Will Harness 的刹车和注意力配额,用来防止 agent 无限搜索、无限返工、无限调用 worker、无限消耗人类注意力。

保留能力:

| 能力 | P0 是否需要 | 说明 |
|---|---:|---|
| max steps | 是 | 防无限 loop |
| max worker runs | 是 | 防 pi/Codex 失控 |
| max retries/revisits | 是 | 防反复返工 |
| max cost/token/time | 是 | 真实运行必须有 |
| verified artifact replenishes budget | 暂缓强调 | 可留内部实现,不是 MVP 第一层卖点 |
| ExistenceBudget 哲学模型 | 暂缓强调 | 放理论文档/白皮书,不主导 BTC MVP |

### DeliveryLedger / AdoptionLedger

外显语义:

> 账本是交付证据链:记录一个复杂答案是怎么被计划、执行、验收、返工和采纳出来的。

Will 不自研 raw tool trace、session transcript、外部 runtime checkpoint。那些由 pi、Codex、OpenClaw、OpenAI Agents SDK、LangGraph 承担。Will 只保留 canonical delivery/adoption ledger:

- 哪个 artifact 被产出;
- 谁产出的;
- 经过什么验证;
- Soul 提了什么反对意见;
- Will 采纳/拒绝了什么;
- 为什么返工;
- 最终报告引用了哪些 accepted artifacts。

## 当前代码收敛方向

| 当前模块/概念 | 决定 |
|---|---|
| `campaigns/schemas.py` | 保留,定义 campaign 领域语言 |
| `campaigns/engine.py` | 强保留,`campaign_tick()` 是 CampaignController 雏形 |
| `campaigns/validators.py` | 保留,artifact acceptance gate |
| `campaigns/executor.py` | 当前仍物化 artifact 与执行 S4 backtest;后续拆 worker/artifact 边界 |
| `controller/` | 新增相位/effect seam;后续从 `campaign_tick()` 抽出 |
| `autonomy/` | 由旧 attention/policy 收敛而来;拥有 StageDecision 与边界 gate |
| `workers/` | 由旧 execution 收敛而来;worker 只产候选 |
| `ledger/` | 由旧 state 收敛而来;append-only truth |
| `artifacts/` | 新增引用/manifest 层;不做 search/fetch/backtest |
| `lenses/` | SoulLens 协议;只读 advisory |

## 明确不做

- 不把 Will 做成通用 coding agent;
- 不自研通用 browser/search/subagent framework;
- 不自研多渠道 OpenClaw 替代品;
- 不让 Soul 写 WillState、campaign cursor、budget、memory、event store;
- 不让 pi/Codex/OpenClaw session 成为 canonical Will state;
- 不把 OpenClaw plugin 私有状态作为 canonical campaign ledger;
- 不在 BTC MVP 前引入 LangGraph / Temporal 作为核心运行时;
- 不把 FundArb 重新拉回当前 MVP 主线;
- 不让 `research/` 成为 core module;
- 不让 `run_step` 或自我认知 loop 重新进入 runtime。

## BTC MVP 成功标准

1. 用户一句"BTC 是什么？怎么交易？怎么盈利？"能触发复杂问题分诊。
2. Will 创建/采纳 BTC campaign。
3. S1-S5 都有真实 artifact。
4. S3 产生可审计 BTC 历史数据缓存,含来源、区间、质量报告。
5. S4 跑出 buy-and-hold / DCA / SMA / cash 等最小回测,数字来自确定性 executor。
6. S5 生成最终 research pack,含证据索引、风险、限制、下一步。
7. 至少一次失败能触发 replan/revisit,而不是糊弄完成。
8. Soul 只做 review,Will 记录采纳/拒绝。
9. pi/OpenClaw 只做身体/壳,不拥有 campaign state。

## 技术选择

| 技术 | 决策 | 原因 |
|---|---|---|
| pi / Codex | adopt as worker | 搜索、repo、patch、test、脚本执行身体 |
| OpenClaw | absorb/adopt as shell later | 入口、渠道、插件、审批 UI,不做 canonical state |
| OpenAI Agents SDK | inspect/adopt as worker/session harness | tools、handoff、guardrails、sessions、tracing 成熟,但不拥有 campaign |
| LangGraph | defer | 等出现真实 branching / HITL / checkpoint 复杂度后再迁移 L3 |
| Temporal | defer | 生产级 durable workflow 很强,但 BTC MVP 当前不需要 |
| Will custom core | keep minimal | 只保留 campaign/artifact/adoption/policy/run limits |

## 下一步

1. 实现 BTC S3 data-acquisition decision loop:公开只读源、本地缓存、第三方数据/API key 候选评估与审批边界。
2. 实现 BTC OHLCV 可审计缓存与数据质量报告。
3. 实现 S5 final research pack synthesis:最终答案、证据索引、风险、限制、下一步。
4. 将 `DelegationClient` 后续泛化为 `WorkerAdapter`。
5. 将 `TaskRun` / `Deliverable` 术语迁移到 `WorkerTask` / `ArtifactAcceptance`。
