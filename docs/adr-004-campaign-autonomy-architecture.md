# ADR-004 — 战役自主架构:Will 自主驱动 BTC 研究全流程

状态:Accepted;B1+B2 已实现(2026-07-03),B3-B5 未实现。地基(L0-L3,见 §3)已实现并有真实冒烟证据;
连接件中 D1(CampaignEnvironment)、D2(goal 绑定+分级回血+结论入记忆)已落地为
`yizhi/environments/campaign.py`、`campaign adopt`、`step --env campaign`,并附带预算统一
(ExistenceBudget 唯一货币)、战役内知识传递、结构化密钥扫描;D3(质量闸迭代回路)、
D4(serve daemon)、D5 的渠道挂起审批仍未实现。配套
[will-agent-architecture.md](will-agent-architecture.md)(四轴模块蓝图)、
[resident-operator-plan.md](resident-operator-plan.md)(R0-R4 常驻形态)、
[will-engine-production-roadmap.md](will-engine-production-roadmap.md)(量化判断力路线)、
[project-status.md](project-status.md)(实现事实)。

一句话:**把"战役"变成意志回路的一个行动环境,让用户只做三件事——立项、授权、审批——其余由 Will 在治理闸内自主推进**。BTC 研究(S1 原理 → S2 场所 → S3 结构 → S4 策略回测)是第一个战役,但架构对任何研究型战役成立。

## 1. 问题

W2 之后,BTC 研究的每一段"路"都已存在且真实跑通过:

- 意志回路 `run_step`(观察→回忆→思考→驱力→意向→提案→策略闸→行动→验证→反思→记忆→判断→校准→快照)——**司机**;
- 战役骨架 `yizhi/campaigns/`(stage/deliverable/验收闸/revisit,事件溯源)——**项目层**;
- W2 TaskRunExecutor(fake / 委派研究 / in-process 回测)——**手**;
- R0 只读委派 + R2 渠道 + web 面板——**受治理的手与嘴**;
- fundarb 确定性管线(queue→results→promotion packet)——**量化判断的数字来源**。

但它们**互不知晓**:`run_step` 不知道战役存在;战役靠人敲 `will campaign run` 才动一格;deliverable 验收结果不回流到意志的判断/记忆/预算。今天"BTC 研究全流程"是**用户驱动的流水线**,不是**Will 的意志行为**。

要让用户"用 Will 实现 BTC 研究",缺的不是能力层,是**连接件**:战役如何成为意志的对象(想推进它、复核它、为它花预算、从它的结果学习)。

## 2. 目标与非目标

**目标**

- 用户视角:`立项(create-btc) → 领养(adopt) → 授权(delegation 手动闸) → 启动(serve) → 只在审批点介入`,S1-S4 由 Will 自主推进并迭代。
- 意志视角:战役进度成为 goal/plan/budget/memory 的一等公民;deliverable 的验收与判断结果驱动下一步(推进/复核/revisit/求助)。
- 治理视角:每一次自主 tick 都过策略闸、花预算、留语义事件;人可随时 approve/kill/note。

**非目标**

- 不做 paper/live 交易授权(S4 只产研究 packet;交易闸永远在本架构之外)。
- 不先建"生成式意志上半环"(愿景自创、连想、default-mode 流,见 will-agent-architecture §5)——本设计用战役结构给**反应式回路**提供持续的"下一步",是上半环的前置脚手架,不是替代。
- 不引入新框架运行时(ADR-001:治理核自研,接缝有界)。

## 3. 分层架构(已建 vs 本设计新增)

```text
 用户控制面   create-btc / adopt / 审批(channel·web) / revisit note / 手动闸配置
────────────────────────────────────────────────────────────────────────
 L4 意志层    run_step: goal·drive·intention·ExistenceBudget·memory·judgment   ✅已建
     ↕ D1 CampaignEnvironment(战役=行动环境)      ← 本设计
     ↕ D2 Goal↔Campaign 绑定 + verified_value 接线 ← 本设计
 L3 战役层    Campaign/Stage/Deliverable/AcceptanceGate/revisit(事件溯源)      ✅已建(W1)
 L2 任务层    TaskRun: kind→能力闸(网络/工具)、TaskBudget                      ✅已建(W2)
 L1 执行层    TaskRunExecutor: fake / 委派研究(R0) / in-process 回测           ✅已建(W2)
 L0 治理层    双墙策略闸·事件store·R2渠道·web面板·手动闸                        ✅已建
     ↕ D4 常驻 daemon(serve)                       ← 本设计(=R3 落地形态)
 工作面      fundarb 管线(ledger→queue→results→packet)·papers·VPS 取数        ✅已建
```

判读:**竖线(层)都在,横线(↕ 连接件)是缺口**。D1/D2 让意志"看见并想要"战役;D3(§4.3)让研究质量闭环;D4 让整个系统不靠人敲命令活着。

## 4. 核心设计决策

### D1 — CampaignEnvironment:战役是意志回路的行动环境

新增 `EnvironmentName.CAMPAIGN` 与 `yizhi/environments/campaign.py`,实现现有 `ActionEnvironment` 协议(observe / propose_actions / run),**不改 run_step 一行控制流**:

- `observe()` → 战役状态观察:cursor、active stage 与其目标、上次 deliverable 的验收结果与验证错误、CampaignBudget 余量、待审批项。战役状态即世界状态。
- `propose_actions(state)` → 结构化 sentinel 提案(与 `yizhi:arbbot-backtest`、`yizhi:delegate` 同一模式,墙一):
  - `yizhi:campaign tick --id <cid>`(PROJECT_WORK 类,dry_run 语义=只产研究产物);
  - `yizhi:campaign revisit --id <cid> --stage <sid> --note <引用判断证据>`;
  - `yizhi:campaign report --id <cid>`(挂审批/汇报,复用 R2)。
- `run(proposal)` → 墙二确定性校验参数(id 存在、stage 合法、note 非空且引用 finding/judgment id)后调用**现有** `campaign_tick`/`revisit_stage`,结果落 `ActionRecord.metrics`(tick status、deliverable id、validation errors)。
- 策略闸新增 campaign 分支:只认 sentinel 三动作;revisit 必须携带证据引用;审批未决的 stage 拒绝 tick(闸在墙里,不在 LLM 嘴上)。
- 意向接线(与现有 `_deterministic_choose` 的字典序一致):endorsed drive=exploratory → `tick`(推进前沿);drive=maintenance/continuity → 复核最近 deliverable(触发 judgment,而非盲目 tick);safety_pressure → 只 `report`。

### D2 — Goal ↔ Campaign 生命周期绑定

新增 `will campaign adopt --id btc-mvp`:

- 创建 PURSUING goal,`goal.metadata.campaign_id = btc-mvp`;plan steps 从 stages 确定性派生(S1..S4),plan cursor 与 campaign cursor 同源(campaign 为准,plan 投影)。
- **verified_value 接线(关键,复用既有原则"预算只认结构化 CONCLUSIVE 判定")**:deliverable ACCEPTED(确定性验收闸通过)构成一次 `verified_value` 证据 → 预算 replenish、plan step advance、校准记录。文本产物本身永远不算价值;算的是"通过了确定性合同验收"这一结构化事实。
- campaign COMPLETED → goal DONE → goal genesis(下一战役或复核型战役);连续 rejected/failed × MAX → goal ABANDONED + 渠道求助。战役预算穷尽 → PAUSED,goal 保持 PURSUING 但意向只剩 `report`(等人)。

### D3 — 判断-迭代回路:验收是形式闸,判断是质量闸

两级闸分工(已有件,只接线):

- **形式闸**(已建,确定性):AcceptanceGate 验产物合同(真实 section、来源非空、密钥扫描、workspace 边界)。过闸=可入账的 verified_value。
- **质量闸**(接线):S4 的数字天然有 `judge_backtest` 确定性判定(KILL/ITERATE/PROMOTE/INSUFFICIENT);S1-S3 文本产物走已定的批判 faculty 决策(docs/README.md:异 LLM critic 提疑 → 确定性探针在拓宽样本上定真伪),critic 结论只产生 `revisit 建议 + 证据`,不推翻账。
- **迭代回路**:judgment=ITERATE → 种 prospective memory("资金费率数据积累 ≥N 天后重测 S4")→ due 时 resurface 到 recall → 意向选 revisit(D1 的证据引用即此判断 id)。人工 note 走渠道 `note` 命令 → 下一 tick 的 revision_notes。这条回路的每个机制(prospective/judgment/revisit)都已存在,缺的只是彼此调用。

### D4 — 常驻 daemon(R3 的落地形态)

`will serve`(单进程,`yizhi/engine/daemon.py::run_resident`,对齐 resident-operator-plan §R3):

```text
loop: drain channel inbox(approve/kill/note 入账)
   → 若存在 campaign goal 且 ExistenceBudget/CampaignBudget 允许
        → run_step(env=campaign) × 每 tick 上限
   → report 可报告事件(判断/验收/求助)
   → sleep(tick 间隔;budget halted → 等待态 + 渠道通知,不退出)
```

不变式:daemon 不引入新权限——它只是把"人敲命令"的节拍器换成时钟;每步仍过全部治理闸。bounded smoke(N tick 干净停)是验证闸。

### D5 — 人的控制面(你怎么用它)

| 时机 | 你做什么 | 系统里发生什么 |
|---|---|---|
| 立项 | `will campaign create-btc` | 战役模板落库 |
| 领养 | `will campaign adopt --id btc-mvp` | PURSUING goal + plan 派生(D2) |
| 授权 | 配置 `[delegation]`(或环境变量) | 真实 worker 手动闸打开;不配则 Will 只能 fake/report |
| 启动 | `will serve` | D4 循环开始自主推进 |
| 观察 | web 面板(含 W1.5 战役页) | 只读投影 + SSE |
| 介入 | 渠道 approve/kill/note;`campaign revisit` | 入 InboundCommand 治理路径,下一 tick 生效 |
| 收获 | `data/campaigns/btc-mvp/` 四份产物 + promotion packet | 事件溯源可全程审计 |

## 5. 安全不变式(继承,不新增权限)

- 双墙不变:意志只能从闸内 sentinel 菜单选动作并在类型化 schema 内填参;worker 只读,落盘只由确定性 executor 写在 workspace 内。
- 预算失败方向安全:ExistenceBudget 耗尽 → halt;CampaignBudget 耗尽 → PAUSED;都不会"抓取"。
- CREDENTIAL/SELF_MODIFY/REPRODUCE 永远硬禁;交易(paper/live)不在 campaign 动作面内。
- 人的每个介入点走同一 InboundCommand 治理路径(web 按钮 = Telegram 命令 = 文件 inbox)。

## 6. Build Order(增量,每步有可证伪验证闸)

| 步 | 内容 | 验证闸 |
|---|---|---|
| B1 | `CampaignEnvironment`(observe + 三 sentinel 动作 + 策略闸分支) | 离线测试:观察含 cursor/验收结果;非法 revisit(无证据)被墙二拒 |
| B2 | `campaign adopt`:goal 绑定 + plan 派生 + verified_value 接线 | 测试:ACCEPTED→预算 replenish/plan advance;REJECTED 不入账 |
| B3 | 判断-迭代回路接线(ITERATE→prospective→revisit;critic→建议) | 测试:ITERATE 种子 due 后意向变 revisit 且携证据 id |
| B4 | `will serve` daemon(R3)+ 挂起审批 + budget 等待态 | bounded smoke:N tick 干净停;halted 时渠道收到通知 |
| B5 | W1.5 战役 web 页(stage/deliverable/验证/修订史投影) | 手动 smoke:面板呈现真实战役进度 |

顺序理由:B1/B2 先让意志"看见并想要"战役(最小可用:人仍可手动 `will step --env campaign` 单步驱动,立即可用);B3 补研究质量闭环;B4 才值得常驻;B5 是观测便利。每步独立提交、离线可测,B4 前系统始终"人按一下走一步",风险单调递增可控。

## 7. 与既有文档的关系

- **will-agent-architecture.md(四轴)**:本设计把 Axis II(动机)在项目工作面上外化——vision→campaign→stage 是 goal 层级的现实投影;D4 daemon 是 Axis III"持续认知"的最小前身(有节拍、无联想)。上半环(愿景自创/连想)仍按其 build order 后置。
- **resident-operator-plan.md**:D4 即 R3 的具体形态;D1 的 report 动作复用 R2;执行层复用 R0。R1(patch)/R4(apply)不受本设计影响。
- **will-engine-production-roadmap.md §5(审议认知缺口)**:战役层就是"工作层级 project/campaign"一行的落地;问题分诊/工作记忆仍缺,不由本设计解决。
- **evaluation-protocol.md**:W2.5("维持项目意图的本地研究 agent")的达标判据可直接用 B1-B4 的验证闸组合度量。

## 8. 决策摘要

| 议题 | 决定 |
|---|---|
| 战役如何被意志驱动 | 战役=ActionEnvironment(D1),不改 run_step 控制流 |
| 产物价值如何入账 | 只认确定性验收闸 ACCEPTED 这一结构化事实(D2),文本永不直接算价值 |
| 研究质量如何闭环 | 形式闸(验收)与质量闸(judgment/critic)分离;ITERATE→prospective→revisit(D3) |
| 自主的形态 | 单进程 serve daemon,时钟换人手,不加新权限(D4) |
| 人的位置 | 立项/授权/审批/note 四个介入点,全部走 InboundCommand 治理路径(D5) |
| 先建什么 | B1→B5 增量;B2 完成即"人单步可用",B4 完成即"无人值守可用" |
