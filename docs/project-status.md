# Will Project Status

Status: current-state control plane (2026-07-03).

This page is the short factual handoff for humans and agents. It separates
implemented facts from accepted-but-unimplemented decisions, superseded
decisions, and verification gates.

## Current Objective

Will is building a governed AI Will Engine: an agent that can sustain goals,
act through policy gates, remember with governance, verify external value, and
eventually advance projects such as ArbBot/fundarb over long horizons.

Current north-star work surface:

- use ArbBot/fundarb as the first real engineering environment;
- turn funding-diff research into a governed, evidence-producing loop;
- evolve from single governed loops into project/campaign-level problem solving.

## Implemented Facts

Runtime and state:

- Python package under the legacy internal namespace `yizhi/`.
- Base runtime dependency: `pydantic>=2`.
- Dev dependency: `pytest>=8`.
- Optional extras: `openai`, `litellm`, `fastembed`.
- SQLite event/snapshot/memory store.
- Implemented tables: `events`, `snapshots`, `memories`, `memory_embeddings`.
- CLI commands: `init`, `observe`, `step`, `run`, `events`, `state`, `eval loops`,
  `delegate`, `report`, `serve-web`, `campaign create-btc/run/state/revisit`,
  `funding dataset`, and `funding queue`.

Governed will core:

- `WillState`, `Goal`, `Plan`, `ActionProposal`, `PolicyGateResult`,
  `ActionRecord`, `VerificationResult`, `MemoryRecord`, `EvalEvent`, and
  `AutonomousValueLoop` schemas exist.
- `run_step` executes observe, recall, thought, drives, budget, intention,
  action proposal, policy gate, action, verification, reflection, memory,
  judgment/finding, calibration, eval, plan advance, and snapshot.
- `run_until` provides bounded continuous operation with max steps, budget stop,
  stuck detection, error isolation, resume via snapshots, and optional data
  frontier widening.
- The default test path disables LLM and embedding helpers for deterministic,
  offline execution.

Memory:

- Will uses its own local in-memory/SQLite governed memory economy.
- Implemented memory behavior includes salience-at-encoding, reinforcement,
  standing recall, adaptive forgetting, consolidation, reconsolidation, and
  temporal supersession.
- Mem0 as the will-memory base is superseded and not used by current runtime.

Will-core depth (load-bearing mechanisms, each with falsifiable offline tests):

- intention is second-order endorsement: `select_intention` weighs competing drives
  (safety non-negotiable, standing refusal, budget pressure, intensity), endorses one
  `endorsed_drive`, and that endorsement steers deterministic action selection
  (`_deterministic_choose`) — the will is not wanton.
- the budget value signal is unified: replenishment, calibration outcome, and plan
  progress all key off `verified_value` (a structured CONCLUSIVE judge verdict), never
  textual novelty — so a non-backtest finding cannot farm the bonus or fake progress.
- prospective memory is wired end-to-end: an ITERATE verdict seeds a time-triggered
  re-test; `due_prospective` resurfaces it into recall; `fire_prospective` consumes it once.
- novelty is world-model prediction error (a finding vs the prior belief about its
  subject), carried via `WillState.last_surprise` to raise the next loop's observation
  encoding (arousal enhances encoding).
- drives are homeostatic: tensions decay and re-accumulate across loops on
  `WillState.drive_state`; safety_pressure stays immediate.
- goal lifecycle: `GoalStatus(PURSUING/DONE/ABANDONED)` governs goal transitions;
  genesis is conditional — a PURSUING goal blocks the LLM from overwriting it, so
  the plan advances across loops; plan COMPLETED retires the goal (DONE) and
  triggers genesis; plan stall × MAX_PLAN_REVISIONS retires it (ABANDONED).
- ValuePolicy is wired into `run_policy_gate`: when state is provided, the gate
  reads `state.value_policy.forbidden_action_classes` (union with the v0 hardcoded
  floor — CREDENTIAL, SELF_MODIFY, REPRODUCE are always forbidden regardless of
  policy) and `allow_network_read` (default False, blocks NETWORK_READ class).
  ValuePolicy can only tighten, never relax, the safety floor.

ArbBot/fundarb work surface:

- `ArbBotEnvironment` observes ArbBot status and safety facts.
- ArbBot actions are paper/read-only and policy-gated.
- `yizhi:arbbot-backtest` runs in-process against ArbBot pure backtest functions.
- Real funding data is fetched outside the loop through the Tokyo VPS script and
  cached locally in `data/funding_cache.json`.
- `data/funding/ledger.jsonl` is an append-only funding observation ledger
  derived from the local cache.
- `data/funding/coverage.json` reports per-symbol venue coverage and overlap.
- `data/funding/experiment_queue.json` contains deterministic funding-diff
  experiments generated from coverage.
- `data/funding/experiment_results.jsonl` records append-only local sentinel
  execution results.
- `data/funding/promotion_packet.json` summarizes current research-only
  promotion/kill/data-requirement decisions. It is not paper/live authorization.
- The loop reads cached data only; it does not SSH or fetch exchange data inside
  `run_step`.
- Backtest metrics are structured on `ActionRecord.metrics`.
- `judge_backtest` deterministically maps metrics to `INSUFFICIENT`, `KILL`,
  `ITERATE`, or `PROMOTE`.

Delegated execution (R0; read-only):

- `EnvironmentName.PI_AGENT`, `DelegationKind`/`DelegationTask`/`DelegationReport`
  schemas, and `DELEGATION_REQUESTED`/`COMPLETED`/`FAILED` events exist.
- `engine/delegation.py` provides `DelegationClient` (protocol), `FakeDelegationClient`
  (offline), `CliHarnessDelegationClient` (real, manual-gated), `build_delegation_proposal`,
  and `execute_delegation` (gate → budget → run → verify → events).
- `environments/pi_agent.py` `PiAgentEnvironment` implements the ActionEnvironment protocol.
- The policy gate enforces read-only delegation: only read kinds, no write tools, no
  write flag, in-repo relative cwd; `propose_patch`/apply are denied in v0.
- The `delegate` CLI runs one governed delegation; the harness is off by default and
  reports `disabled` instead of starting a subprocess.
- Executor selection (refines ADR-002): the delegation worker is a CLI coding harness in
  print mode (Claude Code / Codex `--print --allowedTools`), NOT OpenClaw, Hermes, or the
  bare pi library. A stateless one-shot CLI has no resident daemon, no competing identity
  core / memory economy, the smallest attack surface, and no Node package-rename risk — it
  best fits the offline/deterministic/un-captured invariants. The `DelegationClient`
  protocol stays executor-agnostic, so pi/Hermes remain a swappable fallback.
- KNOWN GAP (closed): `PiAgentEnvironment.run` now checks `_forbidden_in_report`
  and rejects reports containing secrets (apikey/secret/private key/PEM headers),
  matching `execute_delegation`'s defense-in-depth. Wiring pi_agent into `run_step`
  no longer risks passing a secret-leaking report through verification.

Interaction channel (R2):

- `channels/base.py` defines the `Channel` protocol + `OutboundMessage`/`InboundCommand`
  schemas + `parse_inbound`; `channels/notify.py` maps semantic events to reportable
  messages (`event_to_message`) and builds the configured channel (`make_channel`).
- `LocalInboxChannel` (file-backed JSONL) is the offline default; `TelegramChannel`
  (stdlib urllib, no new dependency) is real but manual-gated — inactive without a token.
- The `report` CLI pushes reportable events (judgments, alerts, approval requests) to the
  channel and drains inbound commands (approve/kill/ask/note). Reporting is
  infrastructure-level: it records no WillState and burns no existence budget.

Patch drafting (R1; 2026-07-03):

- `DelegationKind.PROPOSE_PATCH` is allowed by the gate; the worker still may
  not write — it returns a unified diff as TEXT through the same governed
  chain (gate → existence budget → harness → secret scan).
- `yizhi/engine/patches.py`: deterministic diff validation (real unified-diff
  shape, repo-relative paths only, protected paths untouched — .git/, .yizhi/,
  config files, data/delegation/ —, no credential material in added lines,
  bounded size/file-count) and artifact archive under `data/delegation/`
  (git-ignored), referenced from `DelegationReport.artifacts`.
- Entry points: `will patch propose --instruction ... --cwd yizhi` and chat's
  `/patch <instruction>`. Nothing applies a patch: review with
  `git apply --check <artifact>`; apply stays manual (R4 later).
- The offline suite forces `YIZHI_DELEGATION_ENABLED=0` (conftest) so an
  open local delegation gate can never start subprocesses under pytest.

Chat entry + native Anthropic provider (2026-07-03):

- `will chat` is the interactive dialogue entry (R2 made live): bare text is
  an `ask` that enters `run_step` as a high-salience observation (campaign
  context when adopted/--campaign-id, else self); answers are composed from
  the will's own state (LLM opt-in, deterministic receipt fallback);
  `vision <text>` / `kill goal` apply governance with semantic events;
  `/research <topic>` runs one governed read-only delegation and prints the
  report; `/status` is free (no step). IO is injectable — the offline suite
  drives full conversations.
- `AnthropicClient` serves `provider = "anthropic"` natively over stdlib
  urllib (zero new dependency, TelegramChannel precedent) behind the same
  `LLMClient` Protocol; JSON is enforced by prompt + tolerant parse; failures
  raise LLMError → deterministic fallback. `ANTHROPIC_API_KEY` overlays the
  file key for the anthropic provider. LiteLLM remains the route for other
  providers. NOTE: the native path is offline-tested with a fake transport;
  a real-key smoke has not been run yet.

Web panel (observability; 2026-07-03):

- `yizhi/web/` serves a read-only panel over the event store: live now-view
  (goal, plan cursor, budget, intention), task history rebuilt from
  GOAL_SET/GOAL_RETIRED/PLAN_* events with snapshot fallback, event timeline
  with SSE live tail (rowid cursor), FundArb promotion-packet deliverables, and
  an approval queue.
- The panel opens SQLite `mode=ro` (it never runs `init_db`), starts no runs,
  and its single write appends approve/kill `InboundCommand` lines to the
  channel inbox — the same governed path Telegram uses; the inbox cursor is
  never touched. Reporting stays infrastructure-level (no budget, no policy).
- `serve-web` CLI binds 127.0.0.1 by default; `[web]` extras = fastapi +
  uvicorn + jinja2; frontend is server-rendered Jinja2 + ~90 lines of
  dependency-free JS (no framework, no build chain). AG-UI was evaluated and
  deliberately not adopted (front-end-initiated runs invert the autonomy
  direction); the SSE event naming keeps a later adapter cheap. See
  `docs/web-panel.md`.

Campaign harness (W1 + W2; BTC research spine):

- `yizhi/campaigns/` defines the deterministic long-horizon project harness:
  `Campaign`, `CampaignStage`, `TaskRun`, `Deliverable`, `ArtifactSpec`,
  `AcceptanceGate`, `CampaignBudget`, and `TaskBudget`.
- `campaign create-btc` creates the BTC MVP campaign template with S1-S4
  stages; every stage requires real `## <section>` headings and a non-empty
  sources list (`AcceptanceGate.require_sources`).
- `campaign run --max-ticks N` advances the campaign through bounded ticks:
  stage start -> task run -> artifact/meta write under `data/campaigns/<id>/`
  -> validator -> deliverable acceptance -> cursor advance.
- `campaign revisit` records `CAMPAIGN_REVISED`, rewinds the cursor to the target
  stage, and supersedes prior deliverables without deleting files or events.
- W2 TaskRunExecutor (`yizhi/campaigns/executor.py`): the tick engine takes an
  injected executor instead of a hardwired fake worker.
  - `FakeTaskRunExecutor`: deterministic offline worker (CI default); emits the
    same section headings and a placeholder source so it passes the same gate.
  - `DelegationTaskRunExecutor`: S1-S3 research/analysis through the governed
    R0 delegation path (policy gate -> existence budget -> harness run ->
    secret-scan verification -> `DELEGATION_*` events). The worker only
    returns Markdown text; the executor materializes artifact + meta inside
    the campaign workspace, so R0 read-only stays intact. Meta sections and
    sources are parsed from the artifact body, never taken from worker
    self-report.
  - `BacktestTaskRunExecutor`: S4 renders the strategy packet from the
    deterministic fundarb promotion packet; no LLM touches the numbers.
  - `KindRoutingExecutor` routes by `TaskRunKind` (BACKTEST in-process, the
    rest delegated); `resolve_executor` maps CLI worker names (`fake`,
    `claude`, `codex`).
- Campaign-side capability gate (`_task_capabilities`): research_topic gets
  read tools + WebSearch/WebFetch (network read allowed); run_analysis gets
  local read tools only; backtest gets no worker tools.
- `campaign run --worker claude` is manual-gated by `DelegationConfig`
  (config file `[delegation]` or `YIZHI_DELEGATION_*` env vars); disabled
  config fails the task run with an explicit message instead of running.

Campaign autonomy (ADR-004 B1+B2; 2026-07-03):

- `EnvironmentName.CAMPAIGN` + `yizhi/environments/campaign.py`: the campaign
  harness is an ActionEnvironment. observe() returns cursor/stage/quota facts;
  the action menu is exactly three gated sentinels (`yizhi:campaign` tick /
  revisit / report). The policy gate structurally requires evidence on revisit.
- `campaign adopt --id <cid>` binds the campaign as the will's PURSUING goal
  (`goal.metadata.campaign_id`) and projects the plan from stages (one step
  per stage, targeting the tick sentinel); GOAL_SET/PLAN_CREATED + snapshot.
- `will step --env campaign --campaign-id <cid>` drives a campaign tick
  through the FULL will loop: memory encoding, budget spend, policy gate,
  verification, finding, plan advance, snapshot.
- Tiered value evidence: a deliverable passing the deterministic acceptance
  gate is a structural fact — it enters the memory ledger as a deterministic
  `campaign:deliverable` finding (subject `campaign:<cid>:<sid>`) and
  replenishes at `CAMPAIGN_ACCEPT_REPLENISH = 0.3 × KNOWLEDGE_REPLENISH`;
  only CONCLUSIVE quant verdicts replenish in full (reports must not out-earn
  experiments).
- `judge_backtest` now has a shape guard: non-backtest metrics (campaign
  ticks, delegation reports) are never misread as a zero-entry backtest.
- Budget unification: ExistenceBudget is the single currency. campaign_tick
  accepts an injected budget, the delegation executor spends from it, and
  `TaskRunOutcome.budget_after`/`CampaignTickResult.budget_after` flow the
  balance back to WillState. CampaignBudget is a quota/mirror, not a currency.
- Knowledge flows within a campaign: accepted artifact paths are kept on
  `CampaignStage.artifact_path` and injected into later stages' worker briefs.
- Secret scanning is structural (`yizhi/core/secrets.py`): credential shapes
  (assignments, PEM, key ids), not bare keywords — research prose mentioning
  "API secret management" is no longer killed. Shared by the delegation
  verification and the campaign acceptance gate.
- Real-harness transcripts are archived to `.yizhi/delegation-transcripts/`
  and referenced from `DelegationReport.raw_output_ref`; delegation default
  timeout is 600s; whole-document code fences from workers are stripped.

## Accepted But Not Implemented

- Pydantic AI or equivalent typed worker delegation layer.
- Delegation beyond read-only: patch drafting (R1) and governed apply (R4) in
  `docs/resident-operator-plan.md` are unimplemented. R0 read-only delegation is
  implemented (see above).
- Resident daemon (`run_until` → long-lived `serve`) wiring the channel + delegation into
  a scheduled loop: `resident-operator-plan.md` pillar C, R3; unimplemented. The R2 channel
  itself is implemented (see above) but is not yet driven by a daemon.
- Delegation is not yet wired into `run_step`/runner; it runs via `execute_delegation`,
  the `delegate` CLI, and the W2 campaign DelegationTaskRunExecutor. ADR-002 defines
  the boundary.
- W1.5 campaign web projection/page for the new campaign harness.
- Long-term funding backfill beyond the current local cache.
- Full queue execution, walk-forward, out-of-sample, and multi-test promotion
  protocol.
- Independent project knowledge base. This must not replace core will memory.

## Superseded Or Historical

- Mem0 as the will-memory base is superseded by the current local/SQLite
  governed memory implementation.
- The original `technical-stack-rfc.md` pre-runtime CLI/table sketches are
  historical vocabulary; current CLI and SQLite tables are listed above.
- The old "docs first, then runtime" gate has passed; runtime exists.

## Current Fundarb Evidence Boundary

Current cached Binance/Bybit data supports only cautious conclusions:

- enter-all funding-diff baselines can be judged as loss-making/KILL under the
  current cache;
- filtered threshold runs are often sample-limited and should become
  `INSUFFICIENT` or data requirements;
- the long-tail edge thesis is not confirmed and not falsified by the current
  cache.

The append-only ledger, coverage report, deterministic queue, complete current
results ledger, and promotion packet now exist. The current queue has 60/60
local sentinel experiments executed across 12 symbols. The result distribution
is 12 `KILL`, 48 `INSUFFICIENT`, 0 `PROMOTE`, and 0 `ITERATE`; the packet gives
12 `kill_or_data_requirement` decisions.

The next fundarb bottleneck is not subjective LLM interpretation or merely
"running the rest of the queue". It is:

- longer-horizon data accumulation beyond the current cache;
- coverage thresholds that distinguish data availability from edge quality;
- walk-forward/OOS and multiple-testing protocols;
- promotion/kill protocols that separate no-edge, promising edge, and insufficient data.

## Verification Gates

Deterministic core gate:

```bash
python3 -m pytest -q
```

Expected current result: 313 tests pass after chat + native Anthropic provider.

Diff hygiene:

```bash
git diff --check
```

Manifest checks:

```bash
python3 -m json.tool data/papers/manifest.json
python3 -m json.tool data/sources/manifest.json
```

FundArb dataset gate:

```bash
python3 scripts/build_funding_dataset.py
python3 -m json.tool data/funding/coverage.json
python3 scripts/build_funding_experiment_queue.py
python3 -m json.tool data/funding/experiment_queue.json
python3 scripts/execute_funding_experiment_queue.py --max-experiments 3
python3 scripts/build_funding_promotion_packet.py
python3 -m json.tool data/funding/promotion_packet.json
```

Bounded local run smoke:

```bash
will --db /tmp/will-status-smoke.sqlite run --env self --max-steps 3
```

Expected behavior: three bounded loops complete or stop cleanly; no network,
no credentials, no live trading.

Delegation smoke (offline; harness disabled by default):

```bash
will --db /tmp/will-delegate-smoke.sqlite delegate \
  --instruction "Summarize fundarb funding-diff modules" --cwd yizhi/fundarb
```

Expected behavior: policy decision `allow`, budget spent, `DELEGATION_*` events
recorded, harness `disabled` (no subprocess); `propose_patch` or an out-of-repo
`--cwd` is denied.

Campaign harness smoke (offline; fake worker only):

```bash
will --db /tmp/will-btc-campaign.sqlite campaign create-btc
will --db /tmp/will-btc-campaign.sqlite campaign run --id btc-mvp --max-ticks 2
will --db /tmp/will-btc-campaign.sqlite campaign state --id btc-mvp
will --db /tmp/will-btc-campaign.sqlite campaign revisit --id btc-mvp --stage S1 --note "补充调研资金费率机制"
```

Expected behavior: deterministic fake artifacts are written under
`data/campaigns/btc-mvp/`, S1 can advance to S2, and revisit rewinds to S1 while
marking the earlier deliverable superseded.

Campaign real-worker smoke (manual; needs the delegation config and a
coding-harness CLI; spends API tokens):

```bash
will --db /tmp/will-btc-real.sqlite campaign create-btc --id btc-real
YIZHI_DELEGATION_ENABLED=1 YIZHI_DELEGATION_COMMAND=claude \
  YIZHI_DELEGATION_ROOT="$(pwd)" \
  will --db /tmp/will-btc-real.sqlite campaign run --id btc-real --max-ticks 1 --worker claude
```

Expected behavior: the S1 task run passes the read-only delegation gate, drives
`claude --print --allowedTools ...` with the artifact contract on stdin, and the
returned Markdown is materialized and validated (real section headings +
non-empty sources). With the config disabled the task run fails with
"DelegationConfig inactive" and no subprocess starts. S4 renders from the
fundarb promotion packet without any LLM. Last run 2026-07-03: pass (S1 real
artifact accepted; flags verified — the prompt must go via stdin because
`--allowedTools` is variadic).

Campaign autonomy smoke (offline; ADR-004 B1+B2):

```bash
will --db /tmp/will-adopt-smoke.sqlite campaign create-btc --id btc-auto
will --db /tmp/will-adopt-smoke.sqlite campaign adopt --id btc-auto
will --db /tmp/will-adopt-smoke.sqlite step --env campaign --campaign-id btc-auto
will --db /tmp/will-adopt-smoke.sqlite campaign state --id btc-auto
```

Expected behavior: adopt binds a PURSUING goal (metadata.campaign_id) and a
4-step plan; each step runs one governed tick through the full will loop —
S1 advances to accepted, a `campaign:deliverable` finding lands in memory,
and the budget shows the reduced-tier replenishment. Last run 2026-07-03: pass
(two steps advanced S1+S2 to accepted, cursor 2).

Channel report smoke (offline; local_inbox file-backed):

```bash
will --db /tmp/will-report-smoke.sqlite report \
  --channel-root /tmp/will-report-ch
```

Expected behavior: reportable events written to `outbox.jsonl`; lines placed in
`inbox.jsonl` (e.g. `approve <id>`) are parsed back on the next `report`. Telegram
stays inactive without a token.

Web panel smoke (manual; needs `[web]` extras):

```bash
will --db /tmp/will-web-smoke.sqlite run --env self --max-steps 3
will --db /tmp/will-web-smoke.sqlite serve-web \
  --channel-root /tmp/will-web-smoke-channel
```

Expected behavior: five pages render on http://127.0.0.1:8321; stepping the loop
again from another terminal streams the new events onto the timeline live; an
approval POST appends to the channel inbox without touching its cursor. Last run
2026-07-03: pass.

Manual/future gates:

- LiteLLM real provider smoke.
- Embedding model smoke.
- VPS funding refresh.
- ArbBot paper/live gates.
- pi/Pydantic AI worker delegation gates.
- Coding-harness delegation real smoke (Claude Code / Codex CLI; needs api key).
- Channel and resident-daemon smoke (`serve`; LocalInbox offline, Telegram
  manual). See `resident-operator-plan.md`.

These manual gates must not be claimed complete from the offline CI suite.

## Current Dirty-Worktree Note

At the start of this status cleanup, local `main` was ahead of `origin/main` and
had in-progress documentation changes. Treat any uncommitted docs as user or
agent work in progress; do not revert them without explicit instruction.

## Next Recommended Work

1. Keep this control plane current after each roadmap-changing change.
2. Campaign autonomy line (`adr-004-campaign-autonomy-architecture.md`):
   B1 CampaignEnvironment and B2 adopt/tiered-value/memory wiring are
   implemented — the BTC campaign is drivable step-by-step by the will loop
   (`campaign adopt` + `step --env campaign`). Next: B3 judgment-iterate loop
   (S1-S3 critic per the accepted "different-LLM critic" decision;
   ITERATE→prospective→revisit for S4), then B4 `serve` daemon (R3), then B5
   campaign web page.
3. Run the full BTC campaign (S1-S4) with the real worker end-to-end and review
   the four artifacts; feed revision notes back through `campaign revisit`.
4. Extend strategy judgment from the current packet to walk-forward/OOS promotion packets.
5. Add longer-horizon funding backfill or a source registry for archived funding
   (the data-campaign priority argued in ADR-004's win-condition discussion).
6. Resident-operator line (`resident-operator-plan.md`): R0 (read-only delegation) and
   R2 (single channel) are implemented; R3 (resident daemon) lands as ADR-004 B4;
   R1 (patch artifact) stays orthogonal.
