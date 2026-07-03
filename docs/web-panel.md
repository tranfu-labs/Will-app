# Will Web 观测面板（web panel）

状态：Implemented（2026-07-03）。配套 [resident-operator-plan.md](resident-operator-plan.md)（R2 渠道层）、[project-status.md](project-status.md)。

## 0. 定位（治理定性）

面板是**事件库的只读投影 + Liaison 对话前厅 + 渠道 inbox 的一个写入口**，不是第二个控制平面：

- 它回答"agent 现在在干什么、干到哪一步、历史上完成过什么任务"；
- 它**不发起 run**、不改配置、不写事件库、不碰 WillState——Will 的 run 由自身发起（goal genesis / 调度），面板只旁观和应答；
- 它唯一能影响 Will 的写动作是把人的 note/ask/vision/kill/approve 追加到渠道 `inbox.jsonl`（`LocalInboxChannel` 的多写者接缝），由 Will loop 下一次 `poll()` 拉取，和 Telegram 审批走同一条 `InboundCommand` 路径；inbox 游标文件绝不触碰；
- Liaison 对话历史单独存在 `.yizhi/liaison.sqlite`（或测试/调用方显式传入的路径），不进 Will event store、不进 Will memory economy；闲聊不会自动污染高显著性 observation。
- 汇报/观测是基础设施级：不烧 existence budget，不进 policy gate（与 R2 渠道层同一定性）。

数据流单向：

```
Will loop ──写──▶ state.sqlite ──mode=ro 只读──▶ 面板页面 / API / SSE / Liaison tools
人 ──对话──▶ Liaison ──只读查询──▶ 投影层
人 / Liaison ──受限命令──▶ inbox.jsonl ──poll()──▶ Will loop（下一 tick）
```

## 1. 快速开始

```bash
python3 -m pip install -e ".[web]"        # fastapi + uvicorn + jinja2
will serve-web                            # http://127.0.0.1:8321
will --db /tmp/demo.sqlite serve-web --port 8321   # 指定库
```

参数：`--host`（默认 127.0.0.1，远程访问请走 SSH 隧道而不是公网绑定）、`--port`（8321）、
`--channel-root`（审批 inbox 目录，默认取 ChannelConfig）、`--packet`（交付物页的 packet 路径）。

## 2. 页面

| 路由 | 内容 |
|---|---|
| `/` 当前状态 | PURSUING 目标卡、计划进度条（cursor/steps + 停滞/重规划计数）、当前意图与被背书驱力、存续预算仪表（halted 红条警示）、回路计数与惊奇度 |
| `/tasks` 任务历史 | 目标生命周期表（pursuing/done/abandoned 徽章、起止、步骤进度、重规划次数、期间判定 verdict） |
| `/timeline` 事件流 | 全语义事件（可按 EventType 过滤），SSE 实时头插新事件 |
| `/deliverables` 交付物 | 存续预算曲线（快照序列 SVG）、FundArb promotion packet 决策表、最近 JudgmentRendered |
| `/approvals` 审批 | 待审批队列（requires_approval 提案），approve/kill 按钮写 inbox；状态诚实标注"已提交，待 loop 拉取" |
| `/chat` 对话 | Liaison 即时回答状态/进展类问题；note/ask 直发 inbox；vision/kill/approve 生成确认卡，确认后才写 inbox；will outbox 回流同一时间线 |

JSON API 与页面同源同投影：`/api/state`、`/api/tasks`、`/api/events`、`/api/approvals`、
`/api/deliverables`、`POST /api/approvals/{correlation_id}`（body `{"verb": "approve"|"kill"}`，
correlation id 必须对应真实 approval 事件，verb 白名单校验）。
对话 API：`GET /api/chat` 返回 human / liaison / will 三源合并时间线；`POST /api/chat`
默认走 Liaison 自然语言路由；`POST /api/chat/confirm/{action_id}` 确认高风险动作后才写 inbox。

## 3. 实时（SSE）

`GET /stream`：连接即发一次全量 `state`（NowView），此后每 ~1s 用 events 表 rowid 游标
拉新事件，逐条发 `semantic_event` 并跟发刷新后的 `state`。事件命名对齐 AG-UI 风格
（state snapshot/delta over SSE），将来要接 AG-UI 客户端时可在其上加薄翻译层，流本身不用重构。

## 4. 结构

```
yizhi/web/
  projections.py   # 纯函数投影：NowView / TaskView / ApprovalView / 预算曲线（离线可测）
  data.py          # 只读 IO：mode=ro SQLite、inbox 读（不动游标）、inbox 追加、packet 读
  app.py           # FastAPI 工厂：SSR 页面 + JSON API + SSE tail + 审批写入
  templates/       # base/now/tasks/timeline/deliverables/approvals（Jinja2 SSR）
  static/          # app.css + app.js（约 90 行原生 JS：SSE 订阅、审批 POST、实时插行）
yizhi/liaison/
  schemas.py       # LiaisonMessage / LiaisonPendingAction / JSON 决策 schema
  store.py         # 独立会话库（不碰 will store）
  tools.py         # 只读投影工具 + 唯一 inbox 写口
  agent.py         # 确定性路由 + 可选 LLM JSON 决策循环（非法/越权降级）
tests/test_web_projections.py   # 投影纯函数（不依赖 fastapi）
tests/test_web_app.py           # HTTP 层（无 [web] extras 时整体 skip，核心套件不受影响）
tests/test_liaison_*.py          # Liaison 会话、工具、agent 离线测试
```

任务历史是重建出来的：GOAL_SET/GOAL_RETIRED 界定每个目标的时间窗，PLAN_CREATED/PLAN_REPLANNED
按 goal_id 提供步骤进度，窗内的 JUDGMENT_RENDERED 归属该目标；快照兜底合并（确定性默认目标
不发 GOAL_SET，且快照里的 plan 进度比事件更新鲜）。

## 5. 刻意不做的选择

- **无前端框架、无构建链**：交互面积极小（SSE 订阅 + 审批 POST + 过滤），约 90 行原生 JS 完成；
  vendored 一个不可审计的 min.js 与离线优先仓库的不变量相悖。将来多人使用/产品化时，API 层不变，
  展示层可整体替换为 React。
- **不引入 AG-UI/CopilotKit**：其生命周期假设"前端发起 run"，与自主 agent 的方向相反；yizhi 的
  语义事件（intention/policy/judgment/budget）在其 16 种 chat 事件里只能塞 CUSTOM。当前只吸收
  "事件流 + 状态更新"形态；Liaison 是本地前厅，不是第二 run 控制面。
- **不实现完整外部 A2A**：首期只吸收 task/message/artifact/status 的内部语义，Liaison 通过投影与
  inbox 协调；等多 worker / 跨系统互操作成为真实需求，再外化 A2A endpoint。
- **不接 Langfuse 类 LLM 观测平台**：数据模型是 LLM trace，不是意志语义事件。
- **web 进程不用 `yizhi.state.store` 的读函数**：它们都会先 `init_db`（写模式）；面板一律
  `mode=ro` 自建查询，库不存在时渲染空态而不是创建它。

## 6. 验证闸

离线（进 CI）：

```bash
python3 -m pytest tests/test_liaison_store.py tests/test_liaison_tools.py tests/test_liaison_agent.py tests/test_web_projections.py tests/test_web_app.py -q
```

手动冒烟：

```bash
will --db /tmp/will-web-smoke.sqlite run --env self --max-steps 3
will --db /tmp/will-web-smoke.sqlite serve-web --channel-root /tmp/will-web-smoke-channel
# 浏览器开 http://127.0.0.1:8321；另开终端再 step 一次，事件流页应实时插入新事件
```

已于 2026-07-03 用真实 loop 数据完成冒烟：五页渲染、SSE 实时插入（一步 loop 的全部事件实时到达）、
审批写读闭环（pytest 内验证 `LocalInboxChannel.poll()` round-trip 且游标未被面板触碰）。

## 7. 与 IM 渠道、daemon 的关系

- 面板与 Telegram/飞书是并列的交互面：Web 是全量视图，IM 是窄视图（通知+审批），全部汇入同一条
  `InboundCommand` 治理路径。飞书/Lark 适配器 = 实现 `Channel` Protocol 的 send/poll（两者只差
  endpoint 域名），见 resident-operator-plan.md R2。
- R3 常驻 daemon 落地后，daemon 的 tick 循环统一驱动渠道 poll；面板无需改动（它读的是同一个库、
  写的是同一个 inbox）。
