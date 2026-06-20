# 意志（yizhi）— 个人自主智能体 / 数字分身战略深挖

> 日期：2026-06-20
> 目的：在 `RESEARCH.md` 的奠基研究之上，继续聚焦「隐私优先的个人自主智能体 / 会行动的数字分身」这条主线，形成更深的产品认知、竞争地图、MVP 楔子与验证标准。
> 方法：基于当前公开产品资料、官方文档、投资方材料与 `RESEARCH.md` 的技术判断综合。商业数字和融资信息仍需在融资数据库中二次核验；本文件重点沉淀战略方向与产品假设。

---

## 1. 新结论：不要做“更懂你的聊天机器人”，要做“可审计的个人行动系统”

本项目最容易走偏的地方，是把「数字分身」理解成一个更像用户说话、更会聊天、更有陪伴感的 AI。这条路会快速滑向 AI companion，遇到低 ARPU、高流失、伦理敏感和人格突变风险。

更好的定义是：

**意志不是替用户说话的分身，而是替用户维护目标、记忆、判断边界和行动候选的个人行动系统。**

这意味着产品重心从“聊天拟人”转向四个更硬的能力：

| 能力 | 用户真正买单的原因 | 不能退化成什么 |
|---|---|---|
| 持久记忆 | 用户不用反复交代背景，agent 能理解长期项目、偏好、关系和目标 | 纯 RAG 文档问答 |
| 稳定身份 | agent 的判断风格、价值排序、风险边界持续一致 | 会模仿语气的角色扮演 |
| 主动发现 | 在用户没问时发现风险、机会、遗漏和下一步 | 高频打扰通知 |
| 可控行动 | 给出可执行方案，必要时经确认后代办 | 无边界自动操作 |

所以，项目主线应从“personal AI companion”收窄为：

> 面向高价值知识工作者的本地优先 personal agency layer：它持续维护用户的目标、记忆、项目状态和行动候选，并以可审计方式主动提出下一步。

---

## 2. 赛道正在分化：四种“数字分身”不是同一种产品

公开产品和平台资料显示，数字分身/个人 AI 正在分化为四类。它们看起来都叫 digital twin、memory、personal AI，但用户任务和护城河完全不同。

| 类型 | 代表 | 核心任务 | 数据来源 | 商业模式 | 对 yizhi 的启发 |
|---|---|---|---|---|---|
| 系统级个人上下文助手 | Apple Intelligence / Siri、ChatGPT Memory、Google Astra 类方向 | 在 OS / Chat 入口中理解个人上下文并执行应用动作 | 设备、聊天历史、应用内容、文件 | 平台捆绑 / 订阅 | 正面竞争不可取；要做垂直深度和可审计治理 |
| 专家/创作者数字分身 | Delphi、Personal.ai 旧定位 | 替专家回答粉丝/客户重复问题，放大影响力 | 公开内容、课程、播客、文档、问答 | SaaS / creator monetization | 不是本项目起点，但可借鉴“有出处回答”和“个人知识资产” |
| 工作流代理 / 会议邮件代理 | Read AI Ada、会议助手、企业搜索 | 从会议、邮件、消息中总结、检索、推进任务 | 会议、邮件、Slack、CRM、任务系统 | B2B / prosumer | 与 yizhi 目标用户最接近，但要避免只做会议总结 |
| 行为模拟 / 群体数字孪生 | Simile | 模拟人群/个体会如何决策，为企业决策预演 | 深度访谈、调研、行为数据 | B2B enterprise | Phase 3 第二曲线；不是个人 dogfood 起点 |

**战略判断**：yizhi 不应该做“公开人格克隆”或“会议记录工具”，而应该做“个人长期目标与行动状态层”。它可以接会议/邮件/文件作为观察源，但产品价值不等于记录这些源，而是把它们转成长期记忆、目标进度、风险与下一步。

---

## 3. 巨头会吃掉入口，小团队必须占据“窄而深的信任层”

Apple 的方向很清楚：AI 会进入系统应用，理解个人上下文，并能在 Messages、Music、Reminders 等应用里行动。OpenAI 的 ChatGPT Memory 也已经从“用户显式保存的记忆”扩展到“从过去聊天中提取上下文”的方向，并强调用户可以查看、删除和关闭记忆。Limitless 被 Meta 收购后停止新售 Pendant、下线部分录制功能，也说明“环境记忆 + 硬件入口”已经是巨头战场。

这些变化意味着：

1. **入口不属于小团队。** 手机 OS、浏览器、聊天入口、办公套件都会自带个人上下文 AI。
2. **浅层记忆会 commoditize。** “记得用户喜欢什么”会变成基础能力。
3. **真正缺口在信任治理。** 用户会问：它为什么记住这个？什么时候用了这条记忆？这条记忆错了怎么撤回？它准备替我做什么？我能不能审计？

yizhi 的可防守位置不是“比 Siri 更懂手机”，而是：

> 跨工具、跨项目、跨时间的个人目标/记忆治理层，默认本地优先，所有记忆、反思、主动建议和行动候选都有来源、版本和审批状态。

这个位置窄，但有价值。因为高价值知识工作者的痛点不是“找不到一个 AI 聊天”，而是：

- 项目背景分散在不同工具里；
- AI 每次重新理解上下文，认知连续性差；
- 重要目标和限制不会自动重锚定；
- 主动提醒要么没有，要么像噪音；
- 个人偏好/判断风格/风险边界没有可管理的结构；
- 自动化动作不可信，因为无法审计“为什么这么做”。

---

## 4. 目标用户不是所有人，而是“上下文复利很高”的人

第一批用户应该满足三个条件：

1. **上下文密度高**：每天处理多个长期项目、关系、文档、会议和决策。
2. **行动价值高**：一个提醒、一个风险发现、一个少遗漏的 follow-up 能产生明显收益。
3. **愿意训练系统**：愿意每天反馈“这个提醒有用/没用/太打扰/错过了什么”。

推荐优先级：

| 用户类型 | 痛点强度 | 付费意愿 | 数据可得性 | MVP 适合度 | 判断 |
|---|---:|---:|---:|---:|---|
| 创始人 / 独立开发者 | 高 | 中高 | 高 | 高 | 最适合 dogfood；目标、项目、机会、风险都密集 |
| 研究者 / 写作者 | 高 | 中 | 高 | 高 | 适合记忆、引用、研究脉络、选题推进 |
| 产品/工程负责人 | 高 | 中高 | 中 | 中高 | 适合项目状态和决策记忆，但组织权限复杂 |
| 投资人/顾问 | 高 | 高 | 中低 | 中 | 价值高，但隐私和数据接入门槛高 |
| 大众个人助理用户 | 中 | 低 | 高 | 低 | 容易被巨头免费功能覆盖 |

**建议 beachhead**：先做“创始人/研究者/重度知识工作者的 daily agency journal”。它不需要一开始接管所有工具，只要每天把真实工作事件变成可用记忆和主动建议，就能验证核心假设。

---

## 5. MVP 不该从“接入所有数据”开始，而该从“主动性质量”开始

很多个人 AI 产品会从“连接 Gmail/Calendar/Slack/Notion”开始。这看起来有平台感，但对 yizhi 来说不是最优第一步。

原因：

- 数据接入会迅速放大隐私、权限和噪音问题；
- 没有主动性评估时，更多数据只会制造更多错误提醒；
- 早期最稀缺的不是数据量，而是用户对主动建议的反馈信号；
- 真实长期记忆的质量，取决于“写入/反思/更新/删除”策略，而不是源数量。

MVP1 的核心实验应该是：

> 给定每天 5-20 条人工输入或半自动导入的工作事件，yizhi 能否稳定地产生 1-3 条用户认为有价值的主动建议，并持续维护正确的长期记忆？

这比接入 10 个工具更有价值。

---

## 6. 产品楔子：Daily Agency Journal

建议把 Phase 1 命名为 **Daily Agency Journal**，它不是日记产品，而是最小可用的个人行动状态层。

### 6.1 每日工作流

1. 用户输入今天发生的事件：会议纪要、项目进展、聊天片段、想法、阻塞、承诺。
2. 系统把事件转成结构化 observation。
3. 系统写入 memory stream，并计算重要性、相关目标、相关项目、潜在行动。
4. 系统提出 memory candidate：哪些应该长期记住，哪些只是短期上下文。
5. 用户批准或修改进入 core memory / project memory。
6. 系统生成主动建议：风险、遗漏、机会、下一步、等待外部输入。
7. 用户标注每条建议：useful / noisy / wrong / missed。
8. 系统把反馈写入 eval log，用于优化主动性策略。

### 6.2 第一屏不应该是聊天

第一屏应该是“今天它看见了什么、记住了什么、建议你做什么”，而不是一个空白聊天框。

推荐信息结构：

| 区域 | 内容 |
|---|---|
| Today | 今日观察事件、待确认记忆、主动建议 |
| Goals | 当前长期目标、阶段目标、阻塞状态 |
| Memory | core memory、project memory、最近反思、变更历史 |
| Actions | 待确认行动候选、已批准行动、被拒绝行动 |
| Feedback | 主动建议评分、错过事项、噪音统计 |

聊天可以存在，但只是解释、追问和修正的界面，不是产品主体。

---

## 7. 产品护城河：不是模型，而是“记忆治理 + 主动性反馈数据”

本项目真正可积累的资产有三类：

| 资产 | 为什么有壁垒 | 如何积累 |
|---|---|---|
| 个人记忆图谱 | 长期、私密、动态，换产品迁移成本高 | 事件、反思、用户批准、版本历史 |
| 主动性偏好模型 | 每个人对“有用/打扰”的边界不同 | 每条建议的 useful/noisy/wrong/missed 反馈 |
| 行动边界策略 | 用户信任来自可控授权，不是能力炫技 | 权限、审批、回滚、审计日志 |

这三类资产都不是单次 prompt 可以复制的。它们来自长期使用和反馈闭环。

因此，MVP 的指标也不能只看回答质量，而要看：

- 每日主动建议采纳率；
- 噪音率；
- 错过率；
- memory correction rate；
- core memory 回滚次数；
- 每周用户是否愿意继续输入真实事件；
- 用户是否开始把 yizhi 当成“项目状态层”而不是聊天工具。

---

## 8. 技术架构判断：LangGraph + Pydantic 是合适的学习型 MVP spine

结合当前目标，推荐继续把 LangGraph 和 Pydantic 放进 Phase 1，但边界要清楚：

| 组件 | 适合做什么 | 不该做什么 |
|---|---|---|
| Pydantic | observation、memory、reflection、suggestion、feedback、action 的结构化契约 | 不替代产品评估 |
| LangGraph | 有状态流程、checkpoint、human-in-the-loop、可恢复执行 | 不把简单逻辑拆成过度复杂的图 |
| Mem0 | 作为可插拔记忆引擎候选，验证 managed memory 的效果 | 不把核心记忆治理完全交给外部黑盒 |
| Letta | 借鉴 core memory / archival memory / stateful agents 范式 | 不一定直接作为第一版运行时 |
| SQLite | 本地优先、可审计、易备份 | 不承担复杂多人协作权限 |

建议工程原则：

1. **先建自有 memory schema，再接 Mem0 adapter。** 这样即使用外部记忆引擎，也不丢失产品主权。
2. **core memory 必须版本化。** agent 可以提出修改，但不能静默改写。
3. **action candidate 和 action execution 分离。** MVP1 只做候选，不直接执行外部动作。
4. **主动建议必须带来源。** 每条建议必须能追溯到 observation、memory、goal 或 rule。
5. **每个 workflow 节点都可测试。** 不要把“观察→反思→建议”藏在一个大 prompt 里。

---

## 9. 竞争判断：yizhi 的差异化句子

可以用下面这句话约束产品方向：

> yizhi is a private agency journal that turns your daily context into governed memory and proactive action candidates.

中文版本：

> 意志是一个隐私优先的个人行动日志，把你的每日上下文转成可治理的长期记忆和可确认的主动行动候选。

这句话有几个刻意选择：

- **private**：不和公共数字分身混淆。
- **agency journal**：不是聊天、不是陪伴、不是会议记录。
- **daily context**：早期从每天真实事件开始，不假装一口吃掉所有数据源。
- **governed memory**：记忆是可审计、可编辑、可回滚的。
- **proactive action candidates**：主动但不越权，先候选再确认。

---

## 10. 三个必须避免的错位定位

### 10.1 不做“更像我的 AI”

语气模仿和人格扮演有吸引力，但不是最强商业价值。yizhi 的身份稳定性应该体现在“判断标准和行动边界稳定”，而不是“说话像我”。

### 10.2 不做“记录一切”

Limitless/Rewind 的路线说明，环境采集是高价值但高风险战场。早期不应承诺录屏、录音、全量环境记忆。应先从用户主动输入和可控导入开始。

### 10.3 不做“全自动代理”

全自动很容易带来信任崩塌。yizhi 的早期承诺应是：发现、解释、建议、等待确认。行动执行是后续阶段。

---

## 11. Phase 1 建议验收标准

MVP1 不是“能跑起来”，而是通过下面的验证门：

| 验收项 | 标准 |
|---|---|
| 记忆写入 | 每条 observation 能生成结构化 memory candidate，并保留来源 |
| 记忆治理 | core memory 修改必须经用户确认，且保留版本历史 |
| 反思质量 | 多条 observation 能生成可解释 reflection，不凭空扩展事实 |
| 主动建议 | 每日生成 1-3 条建议，每条建议都有来源和行动类型 |
| 反馈闭环 | 用户能标注 useful/noisy/wrong/missed，并写入 eval log |
| 本地优先 | 默认 SQLite 本地存储，密钥不入库、不入日志 |
| 成本护栏 | 每轮 workflow 记录 provider、模型、token/cost 或估算 |
| 可恢复 | LangGraph checkpoint 或等价状态保存能恢复未完成流程 |

---

## 12. 推荐下一步文档/工程顺序

1. `docs/product-brief.md`：把本文件压缩成产品定义、目标用户、非目标。
2. `docs/mvp1.md`：定义 Daily Agency Journal 的范围、用户流程、验收标准。
3. `docs/architecture.md`：定义 observation/memory/reflection/suggestion/action/eval 的数据流。
4. `AGENTS.md`：写入本项目的 agent 操作边界，尤其是隐私、记忆修改、行动确认、验证要求。
5. 最小 Python 工程骨架：Pydantic schema + SQLite store + LangGraph 最小流程 + pytest。

---

## 13. 本轮使用的外部参考

- Personal AI: https://www.personal.ai/
- Delphi: https://www.delphi.ai/
- Read AI: https://www.read.ai/
- Limitless acquisition note: https://www.limitless.ai/
- Apple Intelligence and Siri: https://www.apple.com/apple-intelligence/
- OpenAI ChatGPT Memory: https://openai.com/index/memory-and-new-controls-for-chatgpt/
- OpenAI Memory FAQ: https://help.openai.com/en/articles/8590148-memory-faq
- LangGraph overview and persistence: https://docs.langchain.com/oss/python/langgraph/overview and https://docs.langchain.com/oss/python/langgraph/persistence
- Mem0 overview: https://docs.mem0.ai/platform/overview
- Letta stateful agents: https://docs.letta.com/guides/core-concepts/stateful-agents
- Pydantic AI overview: https://pydantic.dev/docs/ai/overview/
- Simile / Index Ventures: https://www.indexventures.com/perspectives/life-the-universe-and-simile-leading-similes-series-a/ and https://www.indexventures.com/companies/simile/

