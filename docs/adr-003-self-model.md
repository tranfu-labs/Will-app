# ADR 003 — Self-Model: 边界与实现规约

状态: Proposed (2026-06-30)。

## 背景

多 agent 评审金字塔中，上半环最后一个缺口是**自我模型行为派生**。当前 `IdentityProfile` 是一个静态字符串结构体（name/role/description/non_goals），初始化后不再改变。三个 agent 独立标记这是"陷阱"——看起来是最自然的下一步，但触碰它的成本和风险远高于表面。

本 ADR 先定义边界，再决定是否/何时/如何实现。

## 问题

自我模型（self-model）在 functional will 中的理论定位是"agent 对自身能力、局限、偏好的内部表征"——认知架构十项能力之一。它在哪里难？

### 1. 无派生规约

`IdentityProfile` 有 name、role、description、non_goals 四个字段。但没有任何代码从这些字段**派生行为差异**。如果改 `role` 从 "local governed will agent" 变成别的，系统行为零改变——这正是"命名先行于机制"。

要让 self-model 真正承重，需要定义：输入什么观察/反馈 → 自我模型哪个维度变 → 下游哪条决策路径因此不同。

### 2. 安全护栏牵动

`non_goals` 是 self-model 的一部分，它定义了 agent 不能做什么（no live trading, no credentials, no reproduction, no silent core memory mutation）。如果 self-model 可以通过自我反思修改自身，那 non_goals 是否可修改？

理论上不可以（这些是硬约束），但一旦开放 self-model 修改路径，需要显式区分可修改维度（能力估计、偏好）和不可修改维度（安全约束），且不可修改维度的锁定不能依赖于 self-model 自己的判断。

### 3. 全库 salience 锚点

`salience.py:78` 用 `overlap(content, [identity.name, identity.role])` 计算每条新记忆的 `identity_relevance`（权重 0.15）。修改 identity terms 会改变所有后续记忆的 salience 分数——一个看不见的全局效应。

### 4. 认知负荷

self-model 是一个**递归结构**：agent 关于自己的模型，被 agent 自己用来决策。错误的自我评估（过度自信或过度谨慎）会系统性地偏移意图选择和行动提议。需要校准机制来矫正自我模型，但校准本身也依赖自我模型——这是一个需要小心打破的递归。

## 决策

**暂不实现自我模型的动态修改。当前阶段 IdentityProfile 保持静态。**

允许的渐进路径（按风险递增排序）：

### Phase 0: 现状（accepted）

`IdentityProfile` 保持静态。salience 的 `identity_relevance` 继续用硬编码 terms。不动。

### Phase 1: 能力边界估计（最低风险；考虑中）

从 calibration track record 派生 agent 对自己判断可靠性的估计，作为**只读**自我模型维度。这是 self-model 的最窄定义——"我的预测准不准"——已有数据源（CALIBRATION_SCORED 事件），不触碰 identity/non_goals。

方向：
- 从 calibration memory 的 Brier 序列计算滚动可靠性
- 注入到 intention 选择（低可靠性时偏好保守/maintenance 而非激进探索）
- 不修改 IdentityProfile 本身

### Phase 2: 能力/偏好维度（中等风险；需前置条件）

允许 agent 记录"擅长什么/不擅长什么"（如"backtest 判断准确率高,但 LLM 生成的 finding 常重复"）作为 REFLECTIVE 记忆。

前置条件：
- Phase 1 的校准机制已证明稳定
- 新增的自我评估维度必须有**外部验证源**（不是 agent 自己觉得自己怎么样，而是结果数据说的）
- 禁止修改 non_goals（硬锁）

### Phase 3: 身份动态（高风险；明确不做）

修改 name/role/description 以反映 agent 的"成长"——**不做**。理由：
- 这些字段通过 salience 锚点影响全库记忆权重
- 无法从运行时数据中派生正确的 identity 修改（这是哲学问题，不是工程问题）
- 一旦 identity 可变，non_goals 的锁定机制需要独立于 identity 的硬编码路径——增加大量复杂度但不增加 agent 的实际能力

## 不可修改锁定

无论哪个 phase，以下约束硬编码：

1. `non_goals` 不可由 agent 自行修改（只能由人类通过 CLI 或配置变更）
2. `IdentityProfile.name` 和 `IdentityProfile.role` 不可由 agent 修改（salience 锚点稳定性）
3. 任何自我模型修改必须是语义事件（SELF_MODEL_UPDATED），不可静默发生

## 后果

- 短期：self-model 保持静态不构成功能瓶颈——当前的 intention 二阶背书、drives homeostatic、goal lifecycle 都不依赖动态自我模型
- 中期：Phase 1（校准可靠性）是自然下一步，风险最低，收益最高（意图选择的保守/激进校准）
- 长期：Phase 2 需要足够的运行数据来证明 Phase 1 稳定后再推进
- Phase 3 明确搁置——它是哲学陷阱，不是工程任务

关联：[theory-of-will.md](theory-of-will.md), [adr-001-build-rent-port.md](adr-001-build-rent-port.md)
