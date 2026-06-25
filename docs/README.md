# yizhi 架构文档索引

yizhi = 受治理的 AI 意志引擎,北极星=自主驱动 ArbBot 量化研发、持续生产。本目录是架构与决策的记录。

## 文档集

| 文档 | 内容 |
|---|---|
| [adr-001-build-rent-port.md](adr-001-build-rent-port.md) | 核心决策:边界按"层"划(自研治理核 / 租基础设施 / 移植模式 / 不吞框架运行时) |
| [will-engine-production-roadmap.md](will-engine-production-roadmap.md) | 用 ArbBot 持续生产的目标工作流、模块缺口、分阶段计划;funding-diff 假阴性纠正 |
| [yizhi-problems-summary.md](yizhi-problems-summary.md) | "一种策略打天下"的问题清单(①-⑥)+ GitHub 成熟方案调研 + 可租性裁决 |
| [memory-fork-strategy.md](memory-fork-strategy.md) | 记忆基座决策:Mem0 为基座、extend 而非 hard-fork(组合层+pin 版本) |
| [theory-of-will.md](theory-of-will.md) · [theory-of-memory.md](theory-of-memory.md) · [will-agent-architecture.md](will-agent-architecture.md) | 理论基础:功能性意志、记忆经济、四轴模块蓝图 |

## 已定的决策(2026-06)

- **多 LLM 供应层**:租 **LiteLLM**(现有 `LLMClient` Protocol 下加 `LiteLLMClient` 类,Protocol/双墙/离线默认不变)。must be multi-LLM。
- **多 agent 委派层**:租 **Pydantic AI**(多 LLM、pydantic 原生、库非运行时、与 ArbBot 同栈);`engine/delegation.py` 作接缝,预算门控 spawn、子 agent 内重应用双墙。
- **持续运行/计划/记忆经济/预算/双墙/校准**:已自研并测扎实(130 测试)。
- **工程债**:O(L²) 已修,可长跑。

## 待讨论/待定的架构决策(用户新方向,2026-06)→ 已讨论决定

| 议题 | 决定 | 接法/边界 |
|---|---|---|
| **长期/项目记忆** | **✅ 用 mem0,作独立"项目知识库"** | mem0 存 ArbBot 持续知识(试过什么/回测结果/品种覆盖);**意志记忆仍 yizhi 自研经济**(两套分开)。mem0 是档案柜,不治理意志;配多 LLM、计入预算。回到 memory-fork-strategy 原决策 |
| **涌现推进(③)** | **先 ~40 行移植;langgraph 暂不引入** | 真要用 langgraph → 走**审议/执行分层**(langgraph 管审议图、yizhi run_step 管受治理执行,langgraph 永不碰执行边);触发器=审议图真复杂(多 agent 编排)时 |
| **批判 faculty(④)** | **✅ 异 LLM critic 提疑 → 重跑探针验证** | 多 LLM 红利:critic 用不同模型=真不同视角(非内省);LLM 只提"该重测什么",**确定性探针在拓宽样本上定真伪**。直击 funding-diff 假阴性 |
| **多 agent(⑤)** | **✅ 可行但按需(Pydantic AI),别滥用** | 回测数学=纯函数循环**不要 agent**;只对"判断量超单上下文"的部分扇出;预算门控 spawn + 子 agent 内重应用双墙 |

**原则锚点(ADR-001)**:无论用哪个库,治理核(预算/双墙/记忆治理/语义事件)自研;框架以**有界接缝**租用,不让其接管受治理的控制平面。**统一缝**:租库/移植在"审议/检索/委派"低治理层,yizhi 自研守"执行/预算/双墙"高治理核。
