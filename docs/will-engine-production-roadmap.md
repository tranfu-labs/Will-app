# Will 生产路线图 —— 用 ArbBot 实现工程意志与持续生产

状态:Draft(2026-06)。配套 [adr-001-build-rent-port.md](adr-001-build-rent-port.md)。本文记录"Will 自主驱动 ArbBot 量化研发、长期无人值守产出"的目标、模块缺口、架构、计划。

## 0. 关键认知纠正(2026-06,用户拍板)

**funding-diff 不是死路。** ArbBot 之前"naked funding-diff 无边(−20~−22bps)"的结论是**假阴性**——只测了**主流币种**。实际**长尾数百个品种**存在 funding 套利机会。

**这条纠正定义了 Will 的真正使命**:不是"执行既定结论",而是**检查并发现问题、质疑假阴性、扩大搜索空间、发现机会、跑通套利全流程**。"发现 funding-diff 没真死"所需的能力(质疑结论+扩大搜索+批量回测长尾+综合判断)正是 Will 当前缺的审议式问题求解能力(见 §5)。

## 1. 目标工作流(持续量化研发循环)

```
提出/质疑 edge 假设 → M2 可行性研究 → M3 授权地写 spec+参数 → M4 在数据上批量回测
  → 读 Sharpe/calibration → 判 真edge vs 过拟合 → 迭代参数 / 杀 / 晋级 → 累积进组合 → 循环
 ┕━ 受治理:预算(赌注)·记忆(账本)·goal-genesis(追什么)·plan(战役)·策略闸(安全)·calibration
```

ArbBot 工作面**已就绪**(`backtest_spec`/`build_funding_diff_spec`/calibration 纯函数、in-memory、确定性,实测 yizhi 可直接 import 调用)。

## 2. 核心张力 + 解法:参数化授权

"持续生产工程"=**创作产物**(写 spec/参数/代码);yizhi 双墙安全=**只能从固定菜单按索引选**。
**解法:authoring within typed schemas**——动作模型从"选 action[i]"→"选 action[i] + 在声明的类型化 schema 内填参数";墙一=环境声明参数模板+边界,墙二=确定性校验参数在界内再构造调用。**LLM 创作"值"不是"代码",双墙不破**,解锁量化研发 ~80%(扫阈值/费率/持有期/品种集)。更深的代码创作=后续沙箱化 spec-DSL 授权,另议。

## 3. 模块清单(需求优先:✅有 / 🟡部分 / ❌完全没有)

**A. 工作面/ArbBot 集成("路")**:A1 回测探针✅ · A2 参数化授权✅ · A3 量化结果解读🟡 · A4 实验设计(网格+walk-forward+多重检验)🟡 · A5 edge-vs-过拟合裁决🟡 · A6 假设生成/质疑🟡 · A7 数据回填🟡(VPS funding cache 路径已建;append-only ledger + coverage report 已建;长期回填/多源归档仍未建)。

**B. 意志引擎核心("司机",~85% 已建)**:runner✅ · plan-execute✅(浅环境休眠) · 记忆经济✅ · goal-genesis✅ · 双墙安全✅ · 持久续跑✅ · ExistenceBudget🟡(可恢复标量非可失去)。

**C. 持续生产/"工厂"层**:C1 跨多轮战役/组合调度🟡 · C2 在环自我监控🟡 · C4 量化 kill🟡 · C5 真钱安全闸❌(ArbBot 自身锁 live,yizhi 角色=驱动其闸非绕过)。

**D. 审议式认知深度(§5,最根本的缺口)**:问题分诊❌ · 工作记忆/草稿纸❌ · 涌现式推进(边做边发现)🟡 · 发现/批判 faculty🟡 · 协作/委派(多 agent / pi worker)❌ · 工作层级(action/task/project/campaign/portfolio)🟡。

**E. 真"意志"哲学深化**:可失去赌注❌ · 自创愿景❌ · 自我模型❌ · 持续思考/联想❌。

## 4. 是否符合要求(诚实裁决)

司机(意志引擎)**达标**且地基刚夯实(O(L²) 已修,可长跑);路(工作面)**严重不符但便宜**;工厂**不符**;**审议认知深度=最根本不符(yizhi 当前是反应式回路,不会"坐下来解一道难题",§5)**;真意志**部分符合**。**最深未知=量化能力**(funding-diff 长尾能否找到真 edge),A1-A5 建好能测量前完全未知。

## 5. 最根本的缺口:从反应式回路 → 审议式问题求解

用户洞察:人能简单思考也能做复杂项目+多人协作;高考数学大题"只看不动笔"解不出,须一步步计算、发现问题、解决问题。**当前 yizhi 太简单**——每个问题(简单/复杂)都过同一个单动作反应回路,缺审议层:

| 缺的认知层 | 含义 | 现状 |
|---|---|---|
| **问题分诊(元认知)** | "这是一句话能答 vs 要立项的难题?" 简单→直接答;复杂→开战役 | ❌ 一刀切 |
| **工作记忆/草稿纸** | 难题的中间推导、试过的死路、当前子目标(≠长期记忆经济) | ❌ |
| **涌现式推进** | 难题不能全程预规划,走一步看一步、从所见推下一步 | 🟡 plan 是预分解+stall-replan,非真涌现 |
| **发现/批判** | 质疑结论、找假阴性、发现漏掉的机会(=funding-diff 纠正) | 🟡 有 calibration,无"框架/结论对不对" |
| **协作/委派** | 复杂项目派子 agent 分工再整合 | ❌ 单回路 |
| **工作层级** | action→task→project→campaign→portfolio | 🟡 有 action+plan+goal,无 project/组合 |

**结论**:工作面是"路",审议认知是"司机的脑"。简单回路开在深路上仍不会做研究。**北极星同时需要:Phase 1 通路 + 审议认知深度。**

## 6. 分阶段计划(关键路径)

- **Phase 1 通路**(A1 回测探针 + A2 参数化授权 + A3 量化解读)——A1/A2 已落地:把"exit 0"变成真实 funding-diff backtest metrics;A3 仍需深化为量化判断力。
- **Phase 2 量化判断力**(A4 实验设计+walk-forward + A5 edge 裁决)——会迭代/杀/晋级,开始测量量化能力。
- **Phase 1.5 / 贯穿 审议认知**(§5:分诊 + 工作记忆 + 涌现推进 + 发现批判 + 委派)——让 yizhi 能"做复杂项目"而非单步反应。**与 Phase 1/2 交织,不是之后。**
- **Phase 3 持续工厂**(C1 战役/组合 + C2 在环监控 + A6 假设生成,批量扫长尾品种)。
- **Phase 4 真意志+规模**(D 哲学深化 + 驱动 ArbBot paper/live 闸 + A7 数据回填)。
- **形态线(贯穿·正交):常驻自主工程体**——委派写代码(R0/R1)+ 交互层(R2)+ 常驻 daemon(R3)+ 受治理 apply(R4),让 yizhi 搬上服务器、长出手与嘴;守 will core,详见 [resident-operator-plan.md](resident-operator-plan.md)。

债:O(L²) 已修✅。Phase 1 前无硬阻塞。

## 7. 项目状态 · 模块完成度 · 优先级(2026-06)

**一句话状态**:意志引擎核(司机)~90% 已建且测扎实(170 测试、可长跑);工作面(路)从~5%推进到~55%(真实 funding cache + append-only ledger + coverage report + deterministic experiment queue + complete current results ledger + research-only promotion packet + in-process backtest + 参数化授权已建);审议认知层(复杂问题的脑)~25%;工厂/生产层~25%;哲学深化 0%。**司机造好了,路已打通第一段,仍缺审议脑、项目层、OOS/walk-forward 晋级协议、长期数据燃料和受控委派工具面。**

**当前 fundarb 证据边界**:在现有 Binance/Bybit VPS cache 可得窗口下,当前 deterministic queue 已完整执行:12 个 symbols × 5 个阈值 = 60 条实验。结果为 12 个 `KILL`、48 个 `INSUFFICIENT`、0 个 `PROMOTE`、0 个 `ITERATE`;promotion packet 对 12 个 symbols 均给出 `kill_or_data_requirement`。这不是 paper/live 授权。含义是:当前 cache 足以杀掉 enter-all/broad baseline,但 filtered threshold 多数受样本量限制;长尾 edge 论点**未证实也未证伪**。下一瓶颈是 OOS/walk-forward、更长历史/多源数据和晋级/杀死协议。

### 模块完成度

| 层 | 模块 | 完成度 | 备注 |
|---|---|---|---|
| **核心(司机)** | 意志回路 run_step | ✅100% | 170 测试 |
| | 记忆经济(意志记忆) | ✅95% | 巩固"learn"仍字符串归约 |
| | ExistenceBudget | ✅90% | 可恢复标量非可失去(哲学待深化) |
| | 双墙安全/策略闸 · goal-genesis · calibration · 事件溯源 | ✅100% | |
| | 持续运行 runner · plan-execute | ✅90% | plan 浅环境休眠;emergent 升级待做 |
| | **多 LLM 供应层(LiteLLM)** | 🟡60% | `LiteLLMClient` 已在 `LLMClient` Protocol 后;真实多 provider smoke/硬化未完成 |
| **工作面(路)** | **A1 回测探针** | ✅85% | in-process funding-diff backtest sentinel 已建;当前 deterministic queue 已全量执行 |
| | A2 参数化授权 | ✅70% | LLM 可在 env 声明宇宙内 author backtest params;仍需更多 schema/action 类型 |
| | A4 实验设计 · A5 edge裁决 | 🟡40% | deterministic queue、complete current results ledger、research packet 已建;walk-forward、多重检验、OOS 晋级未建 |
| | A6 假设生成 | 🟡30% | authored hypothesis + critique 雏形在;系统性假设工厂未建 |
| | A3 量化结果解读 | 🟡30% | findings 在,需要懂 Sharpe/calibration/persistence/过拟合 |
| | **项目记忆/项目 KB** | ❌0% | Mem0 作为意志记忆基座已废弃;独立项目 KB 未建 |
| | A7 数据回填 | 🟡45% | VPS funding cache 路径、append-only ledger、coverage report 已建;长期回填/多源归档未建 |
| **审议层(脑)** | ① 复杂度分诊 · ② 工作记忆 | ❌0% | |
| | ③ 涌现推进 | 🟡60% | stall-replan 在;emergent-amend 待做 |
| | ④ 批判 faculty | 🟡20% | calibration 在;异 LLM critic 待做 |
| | ⑤ 多 agent / pi worker 委派 | ❌0% | Pydantic AI/pi worker 只是 accepted future seam;当前未实现 runtime/client/environment |
| | ⑥ 工作层级 project/campaign | 🟡55% | action/plan/goal 在;W1 Campaign/Stage/TaskRun/Deliverable/AcceptanceGate 骨架已建;真实 worker、web campaign 页、BTC 实研未建 |
| **工厂层** | C1 战役调度 🟡30% · C2 在环监控 🟡40% · C5 真钱闸 ❌0% | | scorecard 离线非在环 |
| **哲学** | D1可失赌注 · D2自创愿景 · D3自我模型 · D4持续思考 | ❌0% | |

### 优先级(按 杠杆×依赖×北极星×成本/风险 排序)

| 序 | 模块 | 为什么最高优 | 成本 |
|---|---|---|---|
| **P0** | **A3 量化解读 + A4/A5 判断力** | A1/A2 已打通后,下一瓶颈是把 backtest metrics 变成 kill/promote/iterate 决策 | 小-中 |
| **P1** | **① 复杂度分诊** | "工程意志"基石:简单题直接答、难题立项;解锁审议层 | ~40 行 |
| **P1** | **④ 批判(异 LLM)** | **直击 funding-diff**:异模型质疑"只测主流?"+ 拓宽样本重跑 oracle→发现假阴性 | ~100 行 |
| **P1** | **LiteLLM provider 实测/硬化** | 供应层代码已建,需把多 provider 真实跑通并记录 fallback/cost | 极小 |
| **P1.5** | **受治理委派写代码(R0/R1)** | 用户新方向:委派 coding harness CLI(Claude Code/Codex)只读分析→草拟 patch,输出回 yizhi 事件/预算/策略/验证闭环;原 P2 提前。见 [resident-operator-plan.md](resident-operator-plan.md) | 小-中 |
| **P1.5** | **交互层 + 常驻 daemon(R2/R3)** | 单渠道汇报/收指令 + `run_until`→`serve` 长期驻留;让 yizhi 搬上服务器、可多软件交互(多选一) | 中 |
| **P2** | **项目知识库/研究账本** | ArbBot 持续记录推进;跨战役留存发现;不等同于 core will memory | 中(租库或自研接缝) |
| **P2** | ③ emergent-replan + ② 工作记忆 + ⑥ project 层 | 深化复杂问题处理 | 小-中 |
| **P3** | ⑤ 多 agent(按需) · C2 在环监控 · D 哲学深化 | 规模与深度,后置 | 中-大 |

**关键路径(最小可用闭环)**:`A3/A4/A5 量化判断力 → ① 复杂度分诊 → ④ 异模型批判 → 项目层/工作记忆`。A1/A2/LiteLLM 已从"决策"进入"已建待硬化";下一步要让 yizhi 不只是能跑 backtest,而是能判断、迭代、杀掉或晋级策略。**之后再 P2 项目知识库/研究账本、深化审议层。** 形态线(委派写代码/交互层/常驻 daemon,提为 P1.5)与本主线正交,可并行从 R0(离线零风险)起手,详见 [resident-operator-plan.md](resident-operator-plan.md)。
