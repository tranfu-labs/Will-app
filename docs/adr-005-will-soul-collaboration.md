# ADR-005 — Will 与 Soul 协作边界

状态:Accepted direction(2026-07-06);文档共识已落地,运行时代码未实现。

一句话: **Will owns campaign agency; Soul owns methodology critique; humans own authority.**

Will 是受治理的战役推进主体:拥有 campaign contract、controller route、autonomy boundary、budget、policy gate、artifact acceptance 和 append-only ledger。Soul 是 source-grounded 的方法论、世界观、工程标准和质量判断层:拥有 raw sources、evidence chunks、promoted knowledge / SoulDB、methodology、anti-patterns、runtime report 和 eval ledger。

两者的组合目标不是"两个 agent 聊天",而是解决人类工程师同时推进多个项目时的注意力、上下文、判断标准和质量把控瓶颈。Will 负责持续推进;Soul 负责让推进有方法论、有证据、有边界。

## 决策

Soul 对自己是独立核心,对 Will 是外置认知核心。Will 通过受治理协议把 Soul 作为只读 reasoning capability 调用,而不是把 Soul 合并进 Will 的意志核。

推荐形态:

1. Soul 内部保持 library-first:核心逻辑可 pytest、CLI、API、Baseline A/B/C 直接验证。
2. Will 消费 Soul 走 service-first:默认通过 Soul API 或等价 `SoulClientProtocol` 调用。
3. MCP 只能作为 Soul API 之上的 adapter,不直接包 Qdrant/Graphiti/SoulDB。
4. Will 内核只允许薄 judgment lens 插件,不托管 SoulDB、Soul memory 或 Soul runtime。
5. 两项目最多共享极薄 contracts,例如 `EvidenceRef`、`SourceRef`、`CallAudit`、`ErrorEnvelope`;不共享 runtime、ledger、policy gate、budget 或 agent state。

## 非目标

- 不把 Soul 变成 Will 的人格核心、自我模型或 WillState。
- 不让 Soul 直接推进 campaign、扣/补 ExistenceBudget、通过/拒绝 policy gate 或写 Will ledger。
- 不让 Will 直接写 SoulDB、promoted knowledge、raw source registry 或 Soul canonical memory。
- 不把 RAG/vector DB/Mem0 当成 Soul;它们只是 Soul 的基础设施。
- 不做多 agent 群聊作为主架构;多 agent 只能是 typed task delegation / typed lens review。
- 不把 LinBiao/Buffett/Musk 等 Soul 的输出说成目标人物对新问题的真实观点;只能说"基于已蒸馏材料的方法论迁移/应用"。

## 最小协议

第一阶段协议是 `SoulLensReport` + `WillAdoptionRecord`,不是自由文本 `askSoul()`。

Will 发给 Soul 的请求只包含任务必要上下文:

```yaml
SoulCallRequest:
  caller: will
  correlation_id: string
  task:
    type: research|strategy|engineering|campaign_review|reflection|grounding
    title: string
    user_question: string
  context:
    campaign_id: string|null
    stage_id: string|null
    artifact_refs: [string]
    known_facts:
      - fact: string
        source: user|will_event|artifact|tool
    policy_constraints: [string]
  requested_soul:
    soul_id: string
    lens: methodology|worldview|engineering_standard|anti_pattern|risk|grounding|critique
  permission:
    mode: read_only
    allow_external_tools: false
    allow_write_will_state: false
    allow_write_souldb: false
  output_contract:
    format: soul_lens_report_v1
    require_evidence: true
```

Soul 返回建议、证据、边界和不确定性,不能返回命令:

```yaml
SoulLensReport:
  call_id: string
  soul_id: string
  status: ok|partial|blocked|error
  readiness:
    baseline_tag: A|B|C|CAPSULE
    souldb_version: string|null
  summary: string
  recommendations:
    - id: string
      action_type: continue|revisit_recommended|ask_human|gather_data|reject_claim
      target_stage: string|null
      text: string
      confidence: number
      methodology_refs: [string]
      evidence_refs:
        - source_id: string
          chunk_id: string
          grade: A|B|C|D
  critique:
    unsupported_claims: [string]
    anti_patterns: [string]
  boundaries:
    can_support: [string]
    cannot_support: [string]
    requires_live_data: [string]
  audit:
    evidence_coverage: number
    created_at: string
```

Will 必须显式记录是否采纳:

```yaml
WillAdoptionRecord:
  soul_call_id: string
  adopted: true|false|partial
  adopted_recommendation_ids: [string]
  rejection_reasons: [string]
  resulting_campaign_action:
    op: tick|revisit|report|none
    stage_id: string|null
```

没有 `WillAdoptionRecord`,Soul 输出不得改变 Will 的计划、目标、预算、记忆或 campaign cursor。

## BTC MVP 接入点

BTC 战役仍由 Will 自主推进。Soul 只作为质量层加入,不接管数据获取或回测执行。

推荐第一阶段:

- S1 问题理解与研究计划:调用 LinBiao execution lens 检查是否有一线事实获取路径、信息阈值和反二手信息边界;调用 Buffett risk/value lens 检查投资/投机/杠杆/能力圈边界。
- S3 数据获取决策:调用 LinBiao execution lens 检查候选数据源、权限、覆盖年限、缓存路径和数据质量是否足以支持下一步。
- S5 最终研究包:调用 Buffett + LinBiao 做 final_quality_review,检查证据链、风险边界、未证结论和下一步。

S4 回测数字仍由 Will 的确定性 BTC 数据/回测 executor 执行。Soul 只能审查指标含义、过拟合风险和历史外推边界,不得生成或修改回测数字。

## 评估

North Star: Soul-assisted Will 在真实 campaign 中,相对 Will-only 明显提升计划质量、证据纪律、反模式规避和最终交付质量。

1-3 个月验证:

- 至少 2 个真实 campaign 产出 `SoulLensReport`、`WillAdoptionRecord`、阶段 artifact 和最终交付物。
- Will+Soul 与 Will-only 做同题对比,由用户或 rubric 盲评。
- Soul 输出必须包含 evidence refs、methodology refs、boundary notes 和 readiness/baseline tag。
- 审计确认 Soul 未执行工具、未改 WillState、未写 Will memory、未反写 SoulDB。

## 后续实现顺序

1. 文档共识:本 ADR + Soul 对应架构页。
2. 协议实现:typed `SoulClientProtocol` + `SoulLensReport` artifact,仍可先用 fake/local client。
3. BTC S1/S3/S5 可选 Soul review gate。
4. MCP adapter 包在 Soul API 外面。
5. 多 Soul 并行 lens review,由 Will reconcile;不做自由群聊。
