# Module Map — 代码分层一览

> 状态:current facts(2026-07-04)。这是 `yizhi/` 包的**代码分层地图**——每个包属于哪一层、
> 依赖朝哪个方向流。与 [will-agent-architecture.md](will-agent-architecture.md)(意志的四轴*理论*)
> 互补:那篇讲"为什么需要这些模块",本篇讲"代码实际长在哪一层"。

## 分层(依赖自上而下,下层不知道上层)

```text
 入口/交互   cli.py · liaison/(web协调agent + 终端chat) · web/(只读面板) · channels/(传输)
     │
 编排驱动    engine/runner.py(run_until) · engine/daemon.py(常驻) · campaigns/(战役状态机)
     │
 意志认知    engine/loop.py(run_step 17阶段) + faculties:
 (engine/)   thought·drives·intention·judgment·reflection·goals·hypothesis·critique·
             calibration·findings·planning·recall_render·dialogue·budget·memory·llm
     │
 治理边界    policy/(双墙:gates + action_classes) · core/secrets.py(密钥扫描)
     │
 向外的手    execution/(delegation:R0只读委派 · patches:R1草拟) · actions/(命令原语+回滚)
 动作面      environments/(self_repo · arbbot · pi_agent · campaign)
     │
 领域工作面  fundarb/(数据管线) · campaigns/executor.py(fake/委派研究/回测)
     │
 记忆/存储   memory/(记忆经济) · state/(事件store·snapshot·migrations) · core/(schemas·ids·time)
```

## 各包一句话职责

| 包 | 层 | 职责 |
|---|---|---|
| `core/` | 基础 | schemas(所有类型的唯一真相)、ids、time、secrets(结构化密钥扫描) |
| `state/` | 存储 | append-only 事件 store、snapshot、migrations——意志的持久化脊柱 |
| `memory/` | 存储 | 意志记忆经济:salience 编码、巩固、遗忘、排序、双通道召回 |
| `policy/` | 治理 | 双墙:`gates.py`(墙二确定性校验)+ `action_classes`(硬禁三类的底座) |
| `engine/` | 认知 | `run_step` 一次意志循环 + 各认知 faculty;`runner`/`daemon` 是回路驱动 |
| `execution/` | 手 | 向外伸的受治理执行:`delegation`(R0 只读委派手)、`patches`(R1 草拟写手) |
| `actions/` | 手 | 底层命令原语(shell runner)+ rollback 证据 |
| `environments/` | 动作面 | ActionEnvironment 协议的实现:self_repo/arbbot/pi_agent/campaign |
| `campaigns/` | 领域 | 长程战役状态机(S1-S4)、executor(谁干活)、验收闸、事件溯源 |
| `fundarb/` | 领域 | 资金费率数据管线:ledger→coverage→queue→results→packet(确定性) |
| `channels/` | 交互 | 人机传输管道:local_inbox(离线默认)、telegram、notify(事件→消息) |
| `liaison/` | 交互 | `agent`(web 侧只读协调 agent,提案→inbox)、`chat`(终端 REPL) |
| `web/` | 交互 | 只读观测面板(FastAPI + Jinja2),不启动 run |
| `eval/` | 观测 | 循环评估、能力 scorecard、指标 |

## 关键不变式(读代码前先知道)

- **worker 只回文本,落盘归确定性代码**:研究产物、回测 packet、代码 patch 三条线统一——
  外部 worker(Claude Code CLI)永远只返回文本,写盘/校验由 `execution/` + `campaigns/` 的
  确定性代码完成。信任边界在这里,不在 worker 里。
- **ExistenceBudget 是唯一货币**:行动烧钱,只有结构化 CONCLUSIVE 判定 / 验收(0.3×折减)回血;
  CampaignBudget 是配额不是钱。
- **双墙**:墙一=环境只给 sentinel 菜单+类型化参数模板;墙二=`policy/gates.py` 确定性校验。
  LLM 只能选菜单+填参,不能创作命令。
- **事件溯源**:失败与拒绝是一等事件,不是静默 abort。`state/store.py` 是 append-only。

## 已知的层未尽事项(诚实标注,非阻塞)

- `engine/llm.py` 是供应商 plumbing 而非认知 faculty,暂留 engine/(8 处引用,搬迁 churn 高、
  收益低);命名已足够自解释。
- `liaison/` 同时住着 web 协调 agent(`agent.py`,自带 LLM 循环)与终端 REPL(`chat.py`,直接
  用 `engine/dialogue.py`)——两个交互面共处一包但不共享脊柱。可用但非最优;若第三个交互面
  (飞书)出现,应抽出共享的交互 spine。
- `engine/dialogue.py` 是意志侧消化人话的 faculty,横跨"认知/交互"边界;当前留 engine/,
  被 runner/daemon/chat 复用。
