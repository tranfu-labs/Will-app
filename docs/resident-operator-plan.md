# Will 常驻自主工程体执行方案(Resident Autonomous Operator)

状态:Proposed plan(2026-06);**R0、R2 已实现(2026-06-30),R1、R3 已实现(2026-07-03——R1: worker 只回 diff 文本、确定性校验+归档、绝不 apply;R3: `will serve` 常驻 daemon,渠道驱动、预算停=低功耗等待、增量事件推送),R4 仍未实现**。本文定方案与接缝;R0-R3 已落地,R4 仍是下一道安全闸。配套 [adr-001-build-rent-port.md](adr-001-build-rent-port.md)、[adr-002-pi-agent-delegated-execution.md](adr-002-pi-agent-delegated-execution.md)、[will-engine-production-roadmap.md](will-engine-production-roadmap.md)。

本文把"yizhi 从本地 CLI 单步治理回路,演进为**常驻服务器、可受治理地委派写代码、通过单一渠道与人交互**的自主工程体"这条形态演进线,拆成可执行、带验证闸、默认安全的阶段。

## 0. 定位

一句话:让 yizhi 长出**手**(委派写代码)、**嘴**(渠道交互)、**驻地**(常驻 daemon),而**意志核(预算 / 双墙 / 记忆治理 / 验证 / 语义事件)一字不改**。

**对标 OpenClaw**(自托管 24/7、以 messaging 为界面、编排 Claude Code/Codex 等 harness 开 PR):它是做到极致的"手和工作台(harness)"。yizhi 学它的**肢体形态与交互形态**,但二者治理模型相反——OpenClaw 无治理,靠"PR 只开不 merge"的人审兜底;yizhi 每一次委派 / 对外通信 / apply 都必须回到 `提案 → 预算 → policy → 执行 → 验证 → 事件`。**本方案是 ADR-002「pi 是手不是意志核」的落地,以及它向常驻 / 交互形态的延伸。**

不变量(继承 ADR-001,不可破):默认确定性、离线、可复现;每个内在变化都有语义事件;治理核自研、不被框架俘获。**本方案新增的一切都是受治理接缝,不是新底座。**

## 1. 三支柱

| 支柱 | 是什么 | 对应用户诉求 | 现状 |
|---|---|---|---|
| **A 受治理委派写代码** | 委派外部 coding harness CLI:只读分析 → 草拟 patch → (受治理)apply | "写代码、持续工作能力必须强;用 gpt/claude api key 写代码" | R0 只读分析 + R1 patch artifact 已实现;R4 apply 未实现 |
| **B 交互层** | 单渠道 `Channel`:主动汇报关键事件 + 接收人类指令 / 授权 | "以后通过各种软件交互,多选一即可" | R2 单渠道已实现;Telegram 仍需手动配置 |
| **C 常驻运行时** | `run_until` 升级为长期驻留 + 调度,保留预算停 / resume / stuck 检测 | "以后 yizhi 自己跑在服务器" | R3 `will serve` 已实现;真实常驻部署仍需人工启动/运维 |

## 2. 与现有架构 / 路线图的关系(正交补线,不改主线)

这条线**不替换、不改动**量化研发主线(roadmap 的 A1–A7 工作面 + 审议认知层),而是正交补上"通信 / 常驻 / 委派工具面"。两条线的分工:

- roadmap 主线 = 让 yizhi 长出**量化判断脑**(发现 funding-diff 真 edge);
- 本方案 = 让 yizhi 长出**手与嘴,并搬到服务器常驻**。

映射:支柱 A = roadmap §3「⑤ 多 agent / pi worker 委派」+「pi agent 有界委派」(原 P2,**本方案提为 P1.5**,因为它是用户当前最高诉求,且是常驻形态的前提);支柱 B / C = roadmap 此前缺席的新维度。

**全部接缝已在代码中预留**(无需改动意志核):

| 接缝 | 位置 | 改动方式 |
|---|---|---|
| 动作环境协议 | `yizhi/environments/base.py` `ActionEnvironment`(observe/propose_actions/run/verify) | 新增 `PiAgentEnvironment` 实现协议 |
| 环境枚举 | `yizhi/core/schemas.py` `EnvironmentName` | 加 `PI_AGENT = "pi_agent"` |
| 事件类型 | `yizhi/core/schemas.py` `EventType` | 加 `DELEGATION_REQUESTED/COMPLETED/FAILED` |
| 策略闸 | `yizhi/policy/gates.py` `run_policy_gate` | 加 `PI_AGENT` 分支 + 任务 allowlist |
| 预算 | `yizhi/engine/budget.py` `spend`/`replenish`/`can_afford` | 委派成本计入,产出新知识则补充 |
| 事件库 | `yizhi/state/store.py` `append_event` | 任意 aggregate_type/payload,直接记录 |
| 委派客户端 | `yizhi/engine/delegation.py`(新,ADR-002 指定) | `DelegationClient` Protocol + CLI 实现 |
| 命令行 | `yizhi/cli.py` argparse subparsers | 加 `delegate` / `serve` 子命令 |
| 配置 | `yizhi/config.py` | 加 `DelegationConfig` / `ChannelConfig`(默认禁用) |

## 3. 分阶段方案

| 阶段 | 目标 | 触及风险面 | 默认开关 |
|---|---|---|---|
| **R0** ✅ | 委派只读分析 MVP(**已实现 2026-06-30**) | 低(read-only) | 默认禁,显式启用 |
| **R1** ✅ | 委派草拟 patch artifact(不 apply,**已实现 2026-07-03**) | 低-中(worker 零写,diff 即文本) | 手动闸(delegation config) |
| **R2** ✅ | 交互层 MVP(单渠道,**已实现 2026-06-30**) | 中(对外通信) | 默认本地 inbox |
| **R3** ✅ | 常驻 daemon(`will serve`,**已实现 2026-07-03**) | 中(长期运行) | 有界 smoke 默认;常驻由人启动 |
| **R4** | 受治理 apply + 写代码闭环 | 高(self_modify / external_write) | 默认禁,每次人审 |

### R0 — 委派只读分析 MVP  ✅ Implemented(2026-06-30)

**已落地**:`schemas`(`EnvironmentName.PI_AGENT` / `DelegationKind` / `DelegationTask` / `DelegationReport` + `DELEGATION_*` 事件)、`engine/delegation.py`(`DelegationClient` 协议 + `FakeDelegationClient` + `CliHarnessDelegationClient` + `build_delegation_proposal` + `execute_delegation`)、`environments/pi_agent.py`(`PiAgentEnvironment`)、policy 只读 allowlist、`yizhi delegate` CLI、`tests/test_delegation.py`(11 测试);全量 207 绿、`diff --check` clean。真实 harness 调用仍是 manual gate。

**目标**:yizhi 能发起一次受治理委派,让一个 coding harness CLI 对 fundarb / ArbBot 代码做**只读分析**(repo 结构、风险、测试失败原因),返回结构化报告,全程过治理闸。这是用户最在意的"写代码能力"的第一段,从 0 到 1。

**改动 / 接口**:
- `schemas.py`:`EnvironmentName.PI_AGENT`;`EventType.DELEGATION_*`;新增模型
  ```python
  class DelegationTask(YizhiModel):
      id: str
      kind: Literal["analyze_repo", "summarize_tests", "inspect_docs"]  # R0 仅只读
      instruction: str
      cwd: str                      # 受限根目录
      allowed_tools: list[str]      # 传给 harness 的工具白名单
      allow_write: bool = False     # R0 恒 False
      cost: float

  class DelegationReport(YizhiModel):
      task_id: str
      ok: bool
      summary: str
      artifacts: list[str] = []     # 落盘产物路径(R0 为空或只读摘要)
      raw_output_ref: str           # 原始输出存档引用
      cost_spent: float
  ```
- `yizhi/engine/delegation.py`(新):
  ```python
  class DelegationClient(Protocol):
      def run(self, task: DelegationTask) -> DelegationReport: ...

  class CliHarnessDelegationClient:           # subprocess 驱动 Claude Code / Codex CLI
      def __init__(self, config: DelegationConfig) -> None: ...
      def run(self, task: DelegationTask) -> DelegationReport: ...
  ```
  默认禁用(`DelegationConfig.enabled=False`);离线 CI 永不真起 subprocess。
- `policy/gates.py`:`PI_AGENT` 分支——只允许 `kind ∈ {analyze_repo, summarize_tests, inspect_docs}`;`allow_write` 必须为 False;`cwd` 必须在声明的受限根内;禁止 `allowed_tools` 含写 / 网络写 / git commit / push / secrets。
- `budget.py`:委派按 `NETWORK_READ`(2.0)计费;`can_afford` 不足则 BLOCKED。
- `cli.py`:`yizhi delegate --kind analyze_repo --task "..." --cwd ...` 手动触发(便于测试)。
- `tests/test_delegation.py`:用 **fake harness**(不调真 CLI)验证 schema / policy 拒绝越权 / budget 计费 / 三个 DELEGATION 事件落库的确定性闭环。

**治理接入**:`ActionProposal(environment=PI_AGENT, action_class=NETWORK_READ)` → `run_policy_gate` → `spend` → `delegation.run`(fake/real) → `verify`(报告非空 + 无 forbidden pattern)→ `append_event(DELEGATION_COMPLETED)`。

**验证闸**:离线 `pytest` 通过(fake harness);**手动 gate**(不进 CI):真实 harness smoke,需 api key。

**退出标准**:一次委派全链路有事件记录;policy 能拒绝 `allow_write=True` 或越权 cwd / 工具的任务。

### R1 — 委派草拟 patch artifact(不 apply)

**目标**:委派从"只读"升到"草拟 patch candidate",产物为 unified diff,写入 `data/delegation/`,**不自动 apply、不 commit**。

**改动 / 接口**:
- `DelegationTask.kind` 加 `propose_patch`;policy 允许该 kind 在**隔离工作区**写 diff 产物。
- 隔离:用 `git worktree` 或临时副本作为 harness 的 cwd,**harness 写不到主 repo**;或要求 harness 仅输出 diff 文本不落主树。
- `PiAgentEnvironment.propose_actions` 暴露 `propose_patch`;`verify` 检查 artifact 存在 + diff 不含 forbidden pattern。

**验证闸**:patch artifact 生成 + 结构校验;apply 仍是后续阶段的独立受治理动作。

**退出标准**:能产出一份隔离的 patch artifact 并记录事件,主 repo 零改动。

### R2 — 交互层 MVP(单渠道)  ✅ Implemented(2026-06-30)

**已落地**:`yizhi/channels/`——`base.py`(`Channel` 协议 + `OutboundMessage`/`InboundCommand` + `parse_inbound`)、`local_inbox.py`(`LocalInboxChannel`,JSONL,离线默认)、`telegram.py`(`TelegramChannel`,stdlib urllib,无新依赖,manual-gated)、`notify.py`(`event_to_message` 事件→消息映射 + `make_channel` 工厂);`ChannelConfig`;`yizhi report` CLI;`tests/test_channels.py`(11 测试);全量 224 绿。汇报为基础设施级,不烧 will budget;Telegram 默认禁用。

**目标**:常驻 yizhi 能向**一个**渠道主动**汇报**关键事件(JUDGMENT_RENDERED、finding、BUDGET_HALTED、需审批的 patch / external_write),并**接收**简单指令(approve / kill / ask)。对应"多选一交互"。

**改动 / 接口**:
- `yizhi/channels/base.py`(新):
  ```python
  class Channel(Protocol):
      def send(self, msg: OutboundMessage) -> None: ...
      def poll(self) -> list[InboundCommand]: ...
  ```
- 首实现 **`LocalInboxChannel`**(读写本地 JSONL,零外部依赖,可离线测试)作为接口骨架;**`TelegramChannel`** 作为第一个真实适配器(手动 gate)。多渠道**多选一**:接口统一,先接一个。
- 接入点:在 runner 事件发射处加 `notify` 钩子(订阅特定 `EventType` → `Channel.send`);inbound 指令作为新 observation 源 / policy 审批输入。
- **治理定性**:出站汇报 = **基础设施级 notifier**(记事件,不烧 will budget);入站人类指令 = 新 observation / 审批信号。对外发消息若承载内容(非状态汇报)按 `EXTERNAL_WRITE` 受治理。

**验证闸**:`LocalInboxChannel` 离线测试(send/poll 闭环);Telegram 手动 smoke。

**退出标准**:一次 loop 的关键事件能投递到渠道,且渠道指令能作为 observation 进入下一回合。

### R3 — 常驻 daemon + 调度

**目标**:把 `run_until` 包进长期驻留进程:`poll 入站 → run_step(s) → 出站 notify → sleep/调度`,保留**预算停**(halted 时进入低功耗等待人类授权 / 补充,**不自动续命**)、snapshot resume、stuck 检测;支持 cron / interval 触发不同环境的回合。

**改动 / 接口**:
- `yizhi/engine/daemon.py`(新):`run_resident(channels, envs, schedule, db_path)`。
- `cli.py`:`yizhi serve` 子命令;`config` 加 daemon 配置(tick 间隔、每 tick max steps、调度表)。
- 部署:文档化在 VPS / 服务器以 systemd / tmux / nohup 运行(呼应 [data-via-vps.md](data-via-vps.md);daemon 本身**不取交易所数据**,取数仍走 VPS 脚本 → 本机缓存 → 本机回测)。

**验证闸**:bounded daemon smoke(跑 N tick 后干净停);不真联网。

**退出标准**:daemon 能连续跑多 tick、受所有治理闸约束、budget halted 时停在等待态并通过渠道通知。

### R4 — 受治理 apply + 写代码闭环(最敏感,最后做)

**目标**:在 R1 的 patch artifact 上,增加一条**受治理 apply 路径**,形成"yizhi 持续写代码推进项目"的完整闭环——这是 OpenClaw"开 PR 不 merge"安全模型的 yizhi 强化版。

**闭环**:`patch artifact → ActionProposal(SELF_MODIFY/EXTERNAL_WRITE) → policy → 人类经渠道授权 → 隔离分支 apply → 跑测试验证 → 通过则记事件 / 失败则自动 rollback`。

**约束(最严)**:默认禁;开启需显式授权;每次人类经渠道逐一确认;git 隔离分支;测试门;失败 rollback;`ROLLBACK_*` 事件已存在可复用。

**退出标准**:一个 patch 能在隔离分支被授权 apply、跑测试、失败自动回滚,全程事件可审计。

## 4. 委派对象选型(关键:别接错"手")

用户提到 gpt / cursor / claude 三者性质不同,委派对象必须是**可编程的 coding harness CLI**,不是 IDE,也不是裸 LLM API:

| 候选 | 性质 | 用哪家 key | 选型 |
|---|---|---|---|
| **Claude Code CLI** | 可编程 coding harness | Anthropic key | ✅ **首个适配器**(本项目即在其中开发,最顺手) |
| **Codex CLI** | 可编程 coding harness | OpenAI key | ✅ 第二适配器("用 gpt 写代码"经此路) |
| OpenClaude / Aider | 可编程 coding harness | 任意 provider key | ✅ 可作后续适配器 |
| 裸 GPT/Claude API | LLM 推理后端 | 各自 key | 已具备(`LLMClient` 走 LiteLLM),是 yizhi 的**大脑**不是手 |
| **Cursor** | IDE 产品 | — | ✗ **无后台委派 API,不作委派对象** |

**实现**:`CliHarnessDelegationClient` 泛化,经 `DelegationConfig.harness`(命令路径 + 默认 allowed tools)切换 harness。"用 gpt/claude 的 key 写代码" = 选不同 harness,各 harness 用各自 key,yizhi 间接用上所有家。

## 5. 红线(贯穿所有阶段)

1. 每次委派 / apply / 对外通信,必须走 `提案 → 预算 → policy → 执行 → 验证 → 事件`。
2. 委派 harness 默认 **read-only、隔离 cwd、禁 secrets / 网络写 / commit / push**;写与 apply 是独立受治理动作。
3. 不让 harness 决定 memory salience / forgetting / policy / budget / verification —— 它只产 observation / report / artifact / proposal candidate。
4. daemon budget halted **不自动续命**,停在等待人类授权 / 外部验证补充态(ExistenceBudget 哲学)。
5. 交互层不绕过 policy;Cursor 不作后台委派对象。
6. 不让 harness 自主 spawn 持久 agent 或绕过复现策略(ADR-002 §不允许)。

## 6. 重估 / 触发条件

- R0→R1:R0 的只读报告能稳定被 yizhi 结构化吸收为 finding / memory。
- R1→R4:patch artifact 质量稳定,且隔离 / 测试 / rollback 接缝已测固定。
- 开启任一"默认禁"阶段:需显式配置 + 对应验证闸通过 + 红线测试覆盖。
- 触发"扩大 harness 权限"前,ADR-002「重估触发条件」四项必须同时成立。

## 7. 最小落地路径

**实施顺序**:`R0 → R2 → R1 → R3 → R4`。先打通"委派只读 + 能汇报",形成最小可感知闭环,再逐步加 patch、daemon、apply。

**已完成的 R0 起手(纯离线、零风险)**:
1. `schemas.py` 加 `EnvironmentName.PI_AGENT` + `DELEGATION_*` 事件 + `DelegationTask/Report` 模型。
2. `engine/delegation.py` 定义 `DelegationClient` Protocol + `CliHarnessDelegationClient` 桩(默认禁用)。
3. `policy/gates.py` 加 PI_AGENT 只读 allowlist。
4. `tests/test_delegation.py` 用 fake harness 锁住 schema / policy / budget / event 闭环。
5. 全程不真起 subprocess、不联网、不写主 repo;`pytest` 仍全绿。

R0 起手后,R2 渠道骨架、R1 patch artifact、R3 daemon 已继续落地;下一步是只在显式授权下推进 R4 governed apply。
