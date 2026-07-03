# ADR 002 — pi agent 作为有界委派执行器,不是 Will Engine 底座

状态:Accepted(2026-06);分阶段落地见 [resident-operator-plan.md](resident-operator-plan.md)(Proposed, not implemented)。背景:在确认 yizhi 的技术架构时,评估是否把 pi agent 纳入技术栈。pi 是强大的 coding agent harness:支持 CLI/TUI、SDK/RPC、custom tools、skills、extensions、sessions、fork/compact 和工具生态。问题不是“能不能用”,而是“放在哪一层”。

## 决策

**引入 pi agent,但只作为有界外部执行器 / 开发者工具壳 / 委派 worker,不作为 yizhi 的核心底座或主运行时。**

换句话说:

- yizhi owns will:意图、驱动、预算、策略闸、记忆 salience、验证、语义事件仍由 yizhi 自研核决定。
- pi owns workbench:代码库探索、工具调用、patch 草拟、测试摘要、repo 分析、MCP/skills 生态可以由 pi 执行。
- pi 的输出是 observation/report/artifact/proposal candidate,不是治理结论。
- yizhi 调用 pi 前后都必须经过预算、policy gate、事件记录和验证。

## 为什么不能把 pi 当底座

pi 的强项是让模型操作工具完成开放式任务;这非常适合 coding agent workbench,但不是 yizhi 的研究核心。yizhi 的核心资产是受治理的意志核:

- `WillState` / `ActionProposal` / `MemoryRecord` 等领域 schema;
- SQLite 语义事件流与 per-loop snapshot;
- ExistenceBudget 的花费、补充、停止;
- 双墙安全:环境声明可行动作 + deterministic policy gate;
- will-governed memory economy:salience、reinforcement、consolidation、supersession、forgetting;
- calibration / verification / autonomous value loop scoring。

如果 pi 接管主循环,会把这些状态转移塞进通用 harness 抽象,造成三类风险:

1. **治理核被俘获**:预算/策略/记忆/验证变成 pi session 的副产物,而不是 yizhi 的一等语义事件。
2. **确定性变弱**:默认离线、可复现、可测的 v0 不变量被通用 agent runtime 的自由工具调用稀释。
3. **研究对象变形**:yizhi 会从 Will Engine 变成“另一个 coding agent shell”,偏离 functional will 北极星。

因此 pi 不能替代 `run_step`、`run_until`、policy gate、memory store 或 event store。

## 允许的集成模式

### 1. PiDelegationClient(优先)

在 `yizhi/engine/delegation.py` 或等价模块中封装 pi SDK/RPC/subprocess 调用。输入是受限任务,输出是结构化报告。

适用任务:

- 分析一个 repo 的结构和风险;
- 总结测试失败和可能原因;
- 草拟 patch plan 或 patch candidate;
- 搜索 docs/skills/MCP 工具能力;
- 对复杂工程问题做 side analysis。

边界:

- 调用 pi 前产生 `ActionProposal` 或 delegation proposal;
- 由 yizhi budget 决定是否负担该调用;
- 由 policy gate 限制任务类型、根目录、可用工具、是否允许写文件;
- pi 返回后写入语义事件,再由 yizhi 决定是否转成 memory/plan/action。

### 2. PiActionEnvironment(次优,用于工具面)

把 pi 暴露成新的 `ActionEnvironment`,例如 `EnvironmentName.PI_AGENT` 或 `PiAgentEnvironment`。这适合把 pi 当成一个“外部工作面”,与 `ArbBotEnvironment` 同级。

最小 action classes:

- `analyze_repo`:只读分析;
- `summarize_tests`:运行/总结指定测试输出;
- `propose_patch`:生成 patch artifact,不自动 apply;
- `inspect_docs`:读取指定 docs 并生成摘要。

默认禁止:

- 任意 shell 写操作;
- 自动 apply patch;
- git commit/push;
- 读取 secrets 或未授权目录;
- 启动长期 agent/session/reproduction。

### 3. 开发者工作台(立即可用)

pi 可以直接作为人类开发 yizhi/ArbBot 的 harness 使用,不进入 runtime。这个模式零架构风险,适合先积累经验:哪些任务 pi 做得好,哪些输出可被 yizhi 结构化吸收。

### 4. 常驻运行时的异步委派(规划中)

当 yizhi 演进为常驻 daemon(见 [resident-operator-plan.md](resident-operator-plan.md) 支柱 C),委派从"单步同步闭环"扩展为"daemon 内多次异步委派":每次委派仍是受预算/policy/验证治理的 `ActionProposal`,产出经渠道汇报,patch/apply 经渠道由人类审批。daemon budget halted 时不自动续命、不自动委派。此模式不改变本 ADR 的边界,只改变调用节奏。

## 不允许的集成模式

- 不用 pi 替换 `yizhi/engine/loop.py` 的 `run_step`。
- 不用 pi 替换 `yizhi/engine/runner.py` 的 `run_until`。
- 不让 pi 直接写 `WillState` snapshot。
- 不让 pi 决定 memory salience、forgetting、policy decision、budget replenishment 或 verification passed。
- 不把 pi sessions 当作 yizhi 的 canonical event store。
- 不让 pi 自主 spawn persistent agents 或绕过 reproduction policy。

## 与既有技术栈的关系

| 层 | 现决策 | pi 的位置 |
|---|---|---|
| 治理核 | yizhi 自研 | 不进入 |
| 语义事件库 | yizhi SQLite | pi 结果被记录为事件,不替代事件库 |
| LLM 供应层 | LiteLLM/OpenAI behind `LLMClient` | pi 可使用自己的 provider,但成本/输出必须回到 yizhi 记录 |
| 多 agent 委派 | Accepted, not implemented;Pydantic AI 或 typed worker 按需 | pi 是 coding/repo worker 的候选实现之一 |
| 项目记忆 | 当前自研 local/SQLite governed memory;外部项目 KB 未实现 | pi 输出可成为未来项目 KB 候选,不直接成为 core memory |
| 动作环境 | `ActionEnvironment` | pi 可新增为受限 environment |
| 开发者体验 | CLI/TUI/SDK 工具 | pi 是强 workbench |

## 最小落地路径

1. **文档先行**:本 ADR 明确边界,防止“因为 pi 很强所以整吞底座”。
2. **只读 delegation MVP**:新增 `PiDelegationClient` 的接口文档/测试桩,先不引入硬 runtime 依赖。
3. **事件语义**:新增或复用事件记录 delegation request/completion/failure,包含 task、cwd、allowed_tools、output_ref、cost。
4. **policy allowlist**:只允许 read-only repo analysis 和 patch proposal artifact。
5. **验证闭环**:pi 的建议若要变成真实行动,必须重新进入 `ActionProposal -> policy -> run -> verify` 流程。

## 重估触发条件

只有当以下条件同时成立,才重新评估 pi 是否承担更重职责:

- yizhi 的审议层需要大量 coding/repo 操作,而自研工具面明显拖慢进展;
- pi delegation 的输出能稳定被结构化评估,并能提升 Autonomous Value Loop 分数;
- policy/budget/event/memory 边界已通过测试固定;
- 没有出现越权写文件、越权读 secrets、不可复现 session 或事件缺失。

即使触发重估,优先扩大 pi 的 worker 能力,仍不把它升级为 Will Engine 底座。

## 后果

好处:

- 复用 pi 的工具生态、SDK/RPC、skills/extensions/session 能力;
- 避免 yizhi 重造 coding harness;
- 保持 yizhi 的治理核、事件核、记忆核不被框架俘获;
- 给复杂工程任务提供外部“手和工作台”。

代价:

- 需要维护一层 delegation/action environment 接缝;
- 需要定义 pi 输出的结构化协议和审计事件;
- 需要额外测试防止 pi 工具越权。

总体裁决:pi 是 yizhi 的**手**和**工作台**,不是 yizhi 的**意志核**。
