# Will

Will is a local **Autonomous Campaign Harness** for long-running research and
engineering work. It is not a chat agent, coding workbench, browser shell, or
Soul runtime.

The product contract is simple:

```text
Human gives goal + boundary.
Will plans and controls the campaign.
Workers produce candidate outputs.
Artifacts describe evidence and delivery assets.
Soul critiques quality and risk.
Will decides accept / revise / revisit / pause / finalize.
Ledger records the truth.
```

The current MVP remains the **BTC campaign**. Given a vague question such as
"BTC 是什么？怎么交易？怎么盈利？", Will should treat it as a complex task,
create or adopt a BTC campaign, route bounded workers, validate artifacts,
acquire auditable data, run minimal explainable backtests, revisit on failure,
and deliver a complete research pack. The developer's job is not to do the BTC
research manually; it is to make Will capable of completing that loop.

## Architecture

```text
Human    = goal, boundary, optional steering, exception approval
OpenClaw = interaction shell: status, steer, pause, digest, approval UI
Will     = autonomous campaign harness: contracts, controller, autonomy, ledger
Soul     = quality lens: methodology, evidence, risk, engineering standards
pi/Codex/OpenAI/OpenClaw worker = execution body: search, repo, patch, test, browser
```

The core modules are:

| Module | Owns | Does not own |
|---|---|---|
| `will/campaigns/` | Campaign templates, stages, artifact contracts, acceptance gates | Tool execution, ledger storage, Soul judgment |
| `will/controller/` | Tick phases and routing effects | Domain algorithms, worker internals, artifact schemas |
| `will/autonomy/` | Scope, usage, interruption policy, stage decisions, policy gates | Artifact production, ledger writes |
| `will/workers/` | Worker adapters, delegation, patch drafting | Campaign cursor, acceptance, canonical state |
| `will/lenses/` | SoulLens protocol and fake lens | State mutation, campaign advancement |
| `will/ledger/` | Append-only events, snapshots, projections | Reasoning, validation, routing |
| `will/artifacts/` | ArtifactRef, SourceRef, EvidenceRef, DataRef, BacktestRef, DeliveryPack | Search, fetch, backtest, report writing |

Invariant:

```text
Campaign defines required outcome.
Worker produces candidate.
Artifact describes candidate.
Soul critiques candidate.
Autonomy decides whether the boundary permits continuing.
Controller routes the next effect.
Ledger records facts.

No module may own produce + judge + commit at the same time.
```

`research/` is intentionally **not** a core module. BTC research is a campaign
template; data acquisition and backtesting are worker task kinds; evidence/data/
backtest outputs are artifact references.

## BTC MVP

```text
Mission:
  "BTC 是什么？怎么交易？怎么盈利？"

CampaignTemplate:
  btc_research_pack_v1

S1:
  understand the vague problem and create the research plan

S2:
  explain BTC mechanism, trading forms, costs, and risks

S3:
  decide data acquisition path and create auditable BTC data cache

S4:
  run minimal explainable backtests: buy-and-hold, DCA, SMA, cash baseline

S5:
  synthesize final answer, accepted artifacts, evidence, risk, limits, next steps
```

## CLI

Install for development:

```bash
python3 -m pip install -e ".[dev]"
```

Initialize the local ledger:

```bash
will init
```

Create and run the BTC campaign:

```bash
will campaign create-btc
will campaign run --id btc-mvp --max-ticks 2
will campaign state --id btc-mvp
will campaign revisit --id btc-mvp --stage S1 --note "补充数据源评估"
```

Run a bounded worker delegation. Real worker execution is off by default unless
`will.config.toml` explicitly enables it.

```bash
will delegate --instruction "Summarize BTC campaign modules" --cwd will/campaigns
```

Draft a patch without applying it:

```bash
will patch propose --instruction "explain the campaign module boundary" --cwd will
```

## Safety

- No automatic trading.
- No trading credentials.
- No external writes without explicit approval.
- No automatic patch apply, commit, push, or deploy from worker output.
- No external harness owns campaign state, policy, memory, budget, or ledger.
- Soul can review and criticize, but Will decides adoption or rejection.

## Verification

Targeted campaign checks:

```bash
python3 -m pytest tests/test_campaign_executor.py tests/test_campaigns.py -q
```

Full offline suite:

```bash
python3 -m pytest -q
```

Architecture consistency checks:

```bash
rg -n "will\\.(attention|execution|state|policy|engine|memory|liaison|web|channels|environments|actions|eval)" will tests
rg -n "Attention-Aware|will/research|will/fundarb|yizhi" docs will tests
git diff --check -- README.md docs will tests scripts pyproject.toml
```
