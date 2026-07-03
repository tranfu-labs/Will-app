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

Campaign harness (W1; BTC MVP foundation):

- `yizhi/campaigns/` defines the deterministic long-horizon project harness:
  `Campaign`, `CampaignStage`, `TaskRun`, `Deliverable`, `ArtifactSpec`,
  `AcceptanceGate`, `CampaignBudget`, and `TaskBudget`.
- `campaign create-btc` creates the BTC MVP campaign template with S1-S4
  stages, but W1 artifacts are deterministic fake artifacts; no real BTC
  research, no LLM, no network, and no K-line/backtest work is claimed.
- `campaign run --max-ticks N` advances the campaign through bounded ticks:
  stage start -> fake task run -> artifact/meta write under `data/campaigns/<id>/`
  -> validator -> deliverable acceptance -> cursor advance.
- `campaign revisit` records `CAMPAIGN_REVISED`, rewinds the cursor to the target
  stage, and supersedes prior deliverables without deleting files or events.
- W1 completion means the BTC MVP foundation is in place; BTC MVP progress is
  approximately 25%, not a completed BTC research campaign.

## Accepted But Not Implemented

- Pydantic AI or equivalent typed worker delegation layer.
- Delegation beyond read-only: patch drafting (R1) and governed apply (R4) in
  `docs/resident-operator-plan.md` are unimplemented. R0 read-only delegation is
  implemented (see above).
- Resident daemon (`run_until` → long-lived `serve`) wiring the channel + delegation into
  a scheduled loop: `resident-operator-plan.md` pillar C, R3; unimplemented. The R2 channel
  itself is implemented (see above) but is not yet driven by a daemon.
- Delegation is not yet wired into `run_step`/runner; it runs via `execute_delegation`
  and the `delegate` CLI. ADR-002 defines the boundary.
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

Expected current result: 281 tests pass after W1 Campaign Harness.

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
2. Extend strategy judgment from the current packet to walk-forward/OOS promotion packets.
3. Add longer-horizon funding backfill or a source registry for archived funding.
4. Build W1.5 campaign web projection/page for current stage, deliverables,
   validation, and revision history.
5. Build W2 TaskRunExecutor/capability gate, then connect real CLI/pi workers
   behind manual gates.
6. Resident-operator line (`resident-operator-plan.md`): R0 (read-only delegation) and
   R2 (single channel) are implemented; next is R1 (patch artifact) then R3 (resident
   daemon wiring channel + delegation). Orthogonal to the quant-judgment line above.
