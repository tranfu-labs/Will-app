# Will 架构文档索引

Will = 受治理的 AI 意志引擎,北极星=自主驱动 ArbBot 量化研发、持续生产。本目录是架构与决策的记录。`yizhi/` 当前保留为内部 Python namespace 和历史代号,不再作为对外项目名。

## 文档集

| 文档 | 状态 | 内容 |
|---|---|---|
| [project-status.md](project-status.md) | Implemented facts | 当前实现事实、验证门、未实现能力、dirty 状态 |
| [adr-001-build-rent-port.md](adr-001-build-rent-port.md) | Accepted | 核心决策:边界按"层"划(自研治理核 / 租基础设施 / 移植模式 / 不吞框架运行时) |
| [adr-002-pi-agent-delegated-execution.md](adr-002-pi-agent-delegated-execution.md) | Accepted, not implemented | pi agent 决策:可作为有界外部执行器/开发者工作台,不作为 Will Engine 底座 |
| [adr-004-campaign-autonomy-architecture.md](adr-004-campaign-autonomy-architecture.md) | Accepted; B1+B2 implemented | 战役自主架构:CampaignEnvironment + goal↔campaign 绑定 + 分级回血 + 结论入记忆已落地(`campaign adopt` + `step --env campaign`);B3 质量闸迭代 / B4 serve daemon / B5 战役页未实现 |
| [will-engine-production-roadmap.md](will-engine-production-roadmap.md) | Draft roadmap | 用 ArbBot 持续生产的目标工作流、模块缺口、分阶段计划;funding-diff 证据边界 |
| [resident-operator-plan.md](resident-operator-plan.md) | Proposed plan | 常驻自主工程体:委派写代码 + 单渠道交互层 + 常驻 daemon;OpenClaw 对标,守 will core |
| [will-problems-summary.md](will-problems-summary.md) | Accepted diagnosis | "一种策略打天下"的问题清单(①-⑥)+ GitHub 成熟方案调研 + 可租性裁决 |
| [memory-fork-strategy.md](memory-fork-strategy.md) | Superseded | 历史决策记录:曾考虑 Mem0 为基座;当前已反转为自研 local/SQLite governed memory |
| [technical-stack-rfc.md](technical-stack-rfc.md) | Mixed: current + historical RFC | 当前技术栈事实、历史 RFC、未来选项;不要把未来接缝当成已实现 |
| [theory-of-will.md](theory-of-will.md) · [theory-of-memory.md](theory-of-memory.md) · [will-agent-architecture.md](will-agent-architecture.md) | Doctrine | 理论基础:功能性意志、记忆经济、四轴模块蓝图 |
| [module-map.md](module-map.md) | Current facts | 代码分层地图:每个包属于哪一层、依赖方向、关键不变式、已知层未尽事项 |

## 已定的决策(2026-06)

- **多 LLM 供应层**:✅ `LLMClient` Protocol 后已有 OpenAI/LiteLLM client 代码和离线 fallback 测试;真实多 provider smoke 仍未完成。
- **多 agent 委派层**:Accepted, not implemented. 方向是租 **Pydantic AI** 或等价 typed worker 接缝;当前没有 `pydantic-ai` runtime 依赖。
- **pi agent**:Accepted, not implemented. 可纳入技术栈,但只作有界外部执行器/开发者工作台/委派 worker;不替换 `run_step`、policy、budget、memory、event store。见 ADR-002。
- **常驻自主工程体**:Proposed plan, not implemented. 委派写代码(支柱 A,原 P2→P1.5)+ 单渠道交互层(支柱 B)+ 常驻 daemon(支柱 C);OpenClaw 对标,守 will core 不变。见 [resident-operator-plan.md](resident-operator-plan.md)。
- **持续运行/计划/记忆经济/预算/双墙/校准**:已自研并测扎实(170 测试)。
- **FundArb 数据资产**:✅ append-only funding ledger + coverage report + deterministic experiment queue + complete current results ledger + research-only promotion packet 已建;当前队列 60/60 已执行,12 个 symbols 均为 `kill_or_data_requirement`;长期回填/多源归档和 OOS/walk-forward 仍未建。
- **Mem0**:Superseded for will memory. 当前不接入 Mem0 backend;未来若用于独立项目 KB,必须与意志记忆经济分离。
- **工程债**:O(L²) 已修,可长跑。

## 待讨论/待定的架构决策(用户新方向,2026-06)→ 已讨论决定

| 议题 | 决定 | 接法/边界 |
|---|---|---|
| **长期/项目记忆** | **已反转:当前不用 Mem0** | `memory-fork-strategy.md` 已 SUPERSEDED;当前使用自研 local/SQLite governed memory。若未来需要独立项目 KB,再以独立接缝评估,不得治理 WillState/core memory |
| **涌现推进(③)** | **先 ~40 行移植;langgraph 暂不引入** | 真要用 langgraph → 走**审议/执行分层**(langgraph 管审议图、Will `run_step` 管受治理执行,langgraph 永不碰执行边);触发器=审议图真复杂(多 agent 编排)时 |
| **批判 faculty(④)** | **✅ 异 LLM critic 提疑 → 重跑探针验证** | 多 LLM 红利:critic 用不同模型=真不同视角(非内省);LLM 只提"该重测什么",**确定性探针在拓宽样本上定真伪**。直击 funding-diff 假阴性 |
| **多 agent(⑤)** | **Accepted, not implemented(Pydantic AI/typed worker 按需)** | 回测数学=纯函数循环**不要 agent**;只对"判断量超单上下文"的部分扇出;预算门控 spawn + 子 agent 内重应用双墙 |
| **pi agent** | **✅ 作为外部执行器,不作底座** | 用于 repo 分析、测试摘要、patch proposal、skills/MCP 工具面;输出回到 Will 事件/策略/预算/验证闭环,不直接写 WillState 或 core memory |

**原则锚点(ADR-001)**:无论用哪个库,治理核(预算/双墙/记忆治理/语义事件)自研;框架以**有界接缝**租用,不让其接管受治理的控制平面。**统一缝**:租库/移植在"审议/检索/委派"低治理层,Will 自研守"执行/预算/双墙"高治理核。
