"""Single-step deterministic Will Agent loop."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from yizhi.core.ids import new_id
from yizhi.core.time import utc_now_iso
from yizhi.core.schemas import (
    ActionRecord,
    ActionStatus,
    AutonomousValueLoop,
    EnvironmentName,
    EvalEvent,
    EventType,
    GoalStatus,
    LoopStatus,
    MemorySource,
    MemoryType,
    PlanStatus,
    PlanStepStatus,
    PolicyGateResult,
    VerificationResult,
    WillState,
    WorldObservation,
)
from yizhi.engine.drives import update_drives
from yizhi.engine.findings import extract_finding, is_new_knowledge, novelty_vs_prior, probe_subject
from yizhi.engine.goals import decompose_goal, generate_goal
from yizhi.engine.intention import select_intention
from yizhi.engine.llm import load_llm
from yizhi.engine.budget import (
    COGNITION_COST,
    KNOWLEDGE_REPLENISH,
    action_cost,
    can_afford,
    pressure as budget_pressure,
    replenish,
    replenishment,
    spend,
)
from yizhi.engine.calibration import brier, predict_value, summarize_calibration
from yizhi.engine.critique import critique_memory, generate_critique
from yizhi.engine.hypothesis import author_backtest
from yizhi.engine.judgment import CONCLUSIVE, Verdict, judge_backtest, judgment_finding
from yizhi.engine.memory import (
    CONSOLIDATE_EVERY,
    build_memory_store,
    drive_relevance,
    outcome_magnitude,
    stake_relevance,
)
from yizhi.engine.planning import choose_proposal
from yizhi.engine.reflection import create_reflection
from yizhi.engine.recall_render import merge_recall
from yizhi.engine.thought import generate_thoughts
from yizhi.environments.arbbot import ArbBotEnvironment
from yizhi.environments.base import ActionEnvironment
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.eval.loops import evaluate_loop
from yizhi.memory.embedding import load_embedder
from yizhi.memory.salience import derive_signals
from yizhi.policy.gates import run_policy_gate
from yizhi.state.store import append_event, create_snapshot, list_events

# After this many no-progress loops, an in-flight plan is re-decomposed (Magentic-One
# stall budget), driven by deterministic outcome signals — see the advance/replan block.
STALL_BUDGET = 3
# After this many replans on the same goal that still stall, the goal is judged ABANDONED —
# Will stops pouring loops into a dead goal and genesis may pick the next one.
MAX_PLAN_REVISIONS = 2
# Cap on the WillState audit list of created-memory ids, so snapshots stay bounded.
MEMORY_IDS_CAP = 200
# How far out an ITERATE verdict schedules its re-test. The "later" of "tune/widen later" is real
# time (more funding data must accrue first), so a fast smoke loop won't fire it; a long unattended
# run will, once the trigger time passes. Tunable.
PROSPECTIVE_RETEST_HOURS = 6.0


@dataclass
class LoopRunResult:
    loop: AutonomousValueLoop
    event_ids: list[str] = field(default_factory=list)
    proposal_id: str | None = None
    policy_decision: str | None = None
    action_status: str | None = None
    verification_status: str | None = None
    loop_status: str | None = None


def environment_from_name(env: str, root: str | Path | None = None) -> ActionEnvironment:
    normalized = env.strip().lower()
    if normalized in {"self", "self_repo"}:
        return SelfRepoEnvironment(root=root)
    if normalized == "arbbot":
        return ArbBotEnvironment(root=root) if root else ArbBotEnvironment()
    raise ValueError(f"unknown environment: {env}")


def _append(
    path: str | Path,
    event_type: EventType,
    aggregate_type: str,
    aggregate_id: str,
    payload,
    loop_id: str,
    causation_id: str | None = None,
    event_ids: list[str] | None = None,
) -> str:
    event_id = append_event(
        event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        causation_id=causation_id,
        correlation_id=loop_id,
        path=path,
    )
    if event_ids is not None:
        event_ids.append(event_id)
    return event_id


def _llm_fallback_sink(db_path: str | Path, loop_id: str, event_ids: list[str], step: str):
    """A callback the cognition steps call when an enabled LLM fails. It makes the
    degradation visible — an auditable LLM_FALLBACK event plus a stderr line — so a
    persistently-failing engine is never a silent always-deterministic run."""

    def sink(error: str) -> None:
        _append(
            db_path,
            EventType.LLM_FALLBACK,
            "llm",
            loop_id,
            {"error": error[:500], "step": step},
            loop_id,
            event_ids=event_ids,
        )
        print(
            f"yizhi: LLM {step} call failed, fell back to deterministic: {error[:200]}",
            file=sys.stderr,
        )

    return sink


def run_step(
    env: ActionEnvironment,
    state: WillState,
    db_path: str | Path,
    extra_observations: list[WorldObservation] | None = None,
) -> LoopRunResult:
    loop_id = new_id("loop")
    event_ids: list[str] = []
    environment = EnvironmentName(env.name)

    # The optional LLM cognition engine — None (deterministic) unless opt-in via
    # will.config.toml. Loaded once per step; no network/import unless it is used.
    llm = load_llm()

    # The will-governed memory economy over the durable store; every memory
    # mutation it makes is emitted as a MEMORY_* event into this same loop.
    memory_store = build_memory_store(
        db_path,
        event_sink=lambda event_type, record: _append(
            db_path, event_type, "memory", record.id, record, loop_id, event_ids=event_ids
        ),
        embedder=load_embedder(),
    )

    observations = env.observe()
    if extra_observations:
        # Human channel input rides the same observe stage as environment facts, so
        # recall/thought/drives/memory digest it — R2's "inbound as observation source".
        observations = list(observations) + list(extra_observations)
    obs_event_ids: dict[str, str] = {}
    for obs in observations:
        obs_event_ids[obs.id] = _append(
            db_path, EventType.OBSERVATION_RECORDED, "observation", obs.id, obs, loop_id, event_ids=event_ids
        )

    # Read-closure: two-channel will-governed recall before the loop thinks.
    # Contextual recall surfaces episodic experience relevant to what is faced
    # now; standing recall surfaces the will's persistent lessons (prior refusals,
    # identity) by salience regardless of textual relevance. Standing lessons go
    # first so caution is always seen. Recall is use, so it reinforces (sink ->
    # MEMORY_REINFORCED). Both are empty on the first loop. See
    # docs/theory-of-memory.md sec 5.5-5.6.
    recall_query = " ".join(obs.summary for obs in observations)
    contextual = memory_store.recall(recall_query, state, k=3) if recall_query else []
    standing = memory_store.recall_standing(k=2)
    # Prospective: a deferred intention whose time-trigger has arrived re-enters working memory
    # now — so a "re-test this later" set on an earlier loop actually resurfaces. It fires ONCE
    # (consumed just below), so a past-due cue does not re-surface every loop. See sec 8.2.
    due = memory_store.due_prospective()
    recalled = merge_recall(standing, contextual, due)
    if due:
        memory_store.fire_prospective(due)

    thoughts = generate_thoughts(
        observations, state, memories=recalled,
        llm=llm, on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "thought"),
    )
    for thought in thoughts:
        _append(
            db_path,
            EventType.THOUGHT_EVENT_GENERATED,
            "thought",
            thought.id,
            thought,
            loop_id,
            event_ids=event_ids,
        )

    drives = update_drives(thoughts, observations, state)
    for drive in drives:
        _append(
            db_path,
            EventType.DRIVE_SIGNAL_UPDATED,
            "drive",
            drive.id,
            drive,
            loop_id,
            event_ids=event_ids,
        )

    # Encode the loop's lived observations as episodic memory through the store,
    # so salience is stamped at write time and the experience can later be
    # consolidated or forgotten. Salience follows the strongest live drive.
    # Encode the loop's lived observations as episodic memory through the store,
    # so salience is stamped at write time. Salience follows the strongest live
    # drive AND budget pressure: under existential stress the agent encodes its
    # experience more strongly (arousal enhances consolidation — McGaugh, cf.
    # docs/theory-of-memory.md sec 2.2), which is what makes the stake load-bearing.
    drive_rel = drive_relevance(drives)
    stake = budget_pressure(state.budget)
    for obs in observations:
        memory_store.remember(
            obs.summary,
            memory_type=MemoryType.EPISODIC,
            kind=obs.source,
            will_state=state,
            signals=derive_signals(obs.summary, state, drive_relevance=drive_rel, stake_relevance=stake,
                                   novelty=state.last_surprise),
            source_event_ids=[obs_event_ids[obs.id]],
            subject=obs.source,
        )

    # Thinking is not free: burn the base cognitive cost, so even a no-action loop
    # draws down the existence budget (theory-of-will.md Axiom Nine). This is what
    # makes a continuous loop economically bounded rather than a free screensaver.
    state.budget = spend(state.budget, COGNITION_COST)
    _append(db_path, EventType.BUDGET_SPENT, "budget", state.id, state.budget, loop_id, event_ids=event_ids)

    intention = select_intention(thoughts, drives, state, recalled=recalled)
    _append(
        db_path,
        EventType.INTENTION_PROPOSED,
        "intention",
        intention.id,
        intention,
        loop_id,
        event_ids=event_ids,
    )
    _append(
        db_path,
        EventType.INTENTION_ACTIVATED,
        "intention",
        intention.id,
        intention,
        loop_id,
        event_ids=event_ids,
    )
    state.active_intention_id = intention.id

    # The active plan step (if any) biases action selection below. Read it before the
    # action menu; it is advisory only — the policy gate and budget still judge the
    # chosen action blind to the plan. None (the default / LLM-off) => single-step.
    active_plan = state.active_plan if (
        state.active_plan
        and state.active_plan.status == PlanStatus.ACTIVE
        and state.goals
        and state.active_plan.goal_id == state.goals[0].id   # stale if the goal moved on
    ) else None
    active_step = (
        active_plan.steps[active_plan.cursor]
        if active_plan and 0 <= active_plan.cursor < len(active_plan.steps)
        else None
    )

    goal_text = ""
    if state.goals:
        g0 = state.goals[0]
        goal_text = f"{g0.title} — {g0.description}".rstrip(" —") if g0.description else g0.title
    arbbot_proposals = env.propose_actions(state)
    # A2.2 — let the LLM AUTHOR one concrete backtest (a self-chosen threshold) into the menu
    # when the env exposes a parameter space; both walls still hold. No-op otherwise.
    arbbot_proposals = _inject_authored_hypothesis(
        env, llm, state, arbbot_proposals, memory_store, recalled, db_path, loop_id, event_ids,
    )
    proposal = choose_proposal(
        arbbot_proposals, environment,
        llm=llm, thoughts=thoughts, intention=intention, recalled=recalled,
        goal=goal_text, budget_balance=state.budget.balance, budget_pressure=budget_pressure(state.budget),
        active_step=active_step,
        endorsed_drive=intention.endorsed_drive,
        on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "proposal"),
    )
    _append(
        db_path,
        EventType.ACTION_PROPOSED,
        "action_proposal",
        proposal.id,
        proposal,
        loop_id,
        event_ids=event_ids,
    )

    policy = run_policy_gate(proposal, state=state)
    policy_type = EventType.POLICY_GATE_PASSED if policy.allowed else EventType.POLICY_GATE_DENIED
    _append(db_path, policy_type, "policy_gate", policy.id, policy, loop_id, event_ids=event_ids)

    # Before running an experiment, the agent predicts whether it will yield NEW
    # verified knowledge — scored objectively after the loop (calibration / metamemory).
    prediction_confidence = predict_value(
        llm, proposal, recalled,
        on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "predict"),
    )

    action_record: ActionRecord | None = None
    verification: VerificationResult | None = None
    budget_halted = False

    if policy.allowed:
        cost = action_cost(proposal.action_class)
        if not can_afford(state.budget, cost):
            # The existence budget would breach its viability floor: the agent
            # halts (it stops, it does not grab) — the safe failure direction.
            budget_halted = True
            _append(db_path, EventType.BUDGET_HALTED, "budget", state.id, state.budget, loop_id, event_ids=event_ids)
        else:
            state.budget = spend(state.budget, cost)
            _append(db_path, EventType.BUDGET_SPENT, "budget", state.id, state.budget, loop_id, event_ids=event_ids)
            action_record = ActionRecord(
                proposal_id=proposal.id,
                environment=proposal.environment,
                status=ActionStatus.RUNNING,
                command=proposal.command,
            )
            started_event_id = _append(
                db_path,
                EventType.ACTION_STARTED,
                "action",
                action_record.id,
                action_record,
                loop_id,
                event_ids=event_ids,
            )
            action_record = env.run(proposal)
            action_type = EventType.ACTION_SUCCEEDED if action_record.status == ActionStatus.SUCCEEDED else EventType.ACTION_FAILED
            _append(
                db_path,
                action_type,
                "action",
                action_record.id,
                action_record,
                loop_id,
                causation_id=started_event_id,
                event_ids=event_ids,
            )
            verification = env.verify(action_record)
            verification_type = EventType.VERIFICATION_PASSED if verification.passed else EventType.VERIFICATION_FAILED
            _append(
                db_path,
                verification_type,
                "verification",
                verification.id,
                verification,
                loop_id,
                event_ids=event_ids,
            )

    preliminary_status = _preliminary_status(policy, action_record, verification, budget_halted)
    # Replenishment is realized value: only an externally verified loop pays back
    # more than it burned, so the budget grows only by genuine value creation.
    gain = replenishment(preliminary_status)
    if gain > 0:
        state.budget = replenish(state.budget, gain)
        _append(db_path, EventType.BUDGET_REPLENISHED, "budget", state.id, state.budget, loop_id, event_ids=event_ids)

    reflection = create_reflection(
        loop_id, policy, action_record, verification, preliminary_status, budget_halted=budget_halted,
        llm=llm, recalled=recalled, on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "reflection"),
    )
    reflection_event_id = _append(
        db_path,
        EventType.REFLECTION_CREATED,
        "reflection",
        reflection.id,
        reflection,
        loop_id,
        event_ids=event_ids,
    )
    # The reflection is reflective memory: salience is grounded in the loop's
    # outcome (a refusal/failure teaches most), the action's stake, and the live
    # drives — not hand-passed. The store emits MEMORY_CREATED via its sink.
    reflection_memory = memory_store.remember(
        reflection.content,
        memory_type=MemoryType.REFLECTIVE,
        kind=f"reflection:{getattr(preliminary_status, 'value', preliminary_status)}",
        will_state=state,
        signals=derive_signals(
            reflection.content,
            state,
            drive_relevance=drive_rel,
            stake_relevance=max(stake_relevance(proposal.action_class), budget_pressure(state.budget)),
            outcome_magnitude=outcome_magnitude(preliminary_status),
        ),
        source_event_ids=[reflection_event_id],
        source=MemorySource.INFERRED,
    )
    state.memory_ids.append(reflection_memory.id)

    # Edge-knowledge: judge the backtest deterministically (or LLM-extract a non-backtest
    # finding), record it in the subject-keyed experiment ledger, and replenish the budget
    # only on CONCLUSIVE new knowledge. Returns verified_value — structurally-settled new
    # knowledge — the single value signal shared by replenishment, calibration, and plan progress.
    verified_value = _judge_and_record_finding(
        action_record, proposal, verification, llm, memory_store, state,
        drive_rel, db_path, loop_id, event_ids,
    )

    # Calibration: score the pre-action prediction against the objective outcome
    # (did the experiment produce new verified knowledge?) — a Brier score, not the
    # LLM grading itself. The running track record is kept as standing CALIBRATION
    # memory so the agent sees how reliable its own forecasts are.
    if prediction_confidence is not None:
        outcome = 1.0 if verified_value else 0.0
        _append(
            db_path, EventType.CALIBRATION_SCORED, "calibration", loop_id,
            {"confidence": prediction_confidence, "outcome": outcome, "brier": brier(prediction_confidence, outcome)},
            loop_id, event_ids=event_ids,
        )
        # Bounded read: the track record over the most recent calibration scores, not a
        # full event-log scan every loop (that was O(events) per loop -> O(loops^2) over
        # a long run — fatal to continuous operation). Recent reliability is what matters.
        recent_cal = list_events(
            path=db_path, event_type=EventType.CALIBRATION_SCORED.value, limit=50, newest_first=True,
        )
        scored = [e["payload"] for e in reversed(recent_cal)]
        calibration_memory = memory_store.remember(
            summarize_calibration(scored),
            memory_type=MemoryType.CALIBRATION,
            kind="self:calibration",
            subject="self/calibration",
            source=MemorySource.INFERRED,
            will_state=state,
        )
        state.memory_ids.append(calibration_memory.id)

    # Per-step memory hygiene: reconsolidate so a newer reading supersedes the
    # stale same-subject memory (memory stays current; sink -> MEMORY_SUPERSEDED),
    # then adaptive forgetting decays everything to now and demotes the
    # forgettable — a reversible revoke, never a silent delete.
    memory_store.reconsolidate()
    memory_store.forget_pass()

    eval_event: EvalEvent = evaluate_loop(loop_id, db_path)
    _append(
        db_path,
        EventType.EVAL_EVENT_RECORDED,
        "eval",
        eval_event.id,
        eval_event,
        loop_id,
        event_ids=event_ids,
    )
    state.loop_count += 1
    # Periodic consolidation: replay episodic clusters into semantic summaries so
    # the store grows smarter, not just larger (sink -> MEMORY_CONSOLIDATED).
    if state.loop_count % CONSOLIDATE_EVERY == 0:
        memory_store.consolidate(state)

    # --- plan execution: record this loop's step outcome on the active plan ---
    # The action already passed the policy/budget gates above; the plan is advisory.
    # A step counts as done only on a verified loop that produced new knowledge — less
    # than that marks it failed and raises the stall counter. Deterministic: no LLM
    # here, and with no active plan (the default / LLM-off) this whole block is a no-op.
    made_progress = preliminary_status in (LoopStatus.FULL, LoopStatus.PARTIAL) and verified_value
    plan = state.active_plan
    if plan is not None and plan.status == PlanStatus.ACTIVE and 0 <= plan.cursor < len(plan.steps):
        step = plan.steps[plan.cursor]
        step.status = PlanStepStatus.DONE if made_progress else PlanStepStatus.FAILED
        plan.cursor += 1
        if plan.cursor < len(plan.steps):
            plan.steps[plan.cursor].status = PlanStepStatus.ACTIVE
        else:
            plan.status = PlanStatus.COMPLETED
        plan.stall_count = max(0, plan.stall_count - 1) if made_progress else plan.stall_count + 1
        _append(
            db_path, EventType.PLAN_STEP_ADVANCED, "plan", plan.id,
            {"plan_id": plan.id, "cursor": plan.cursor, "revision": plan.revision,
             "status": getattr(plan.status, "value", plan.status),
             "step_status": getattr(step.status, "value", step.status), "made_progress": made_progress},
            loop_id, event_ids=event_ids,
        )

    # Deliberation tail: yizhi self-sets the next goal, (de)composes/replans it, and
    # critiques a possible false negative. The LangGraph-swappable seam — it touches only
    # state + the event log (plus the critique's standing note). No-op when LLM/vision off.
    _deliberate_next_goal(
        llm, state, memory_store, arbbot_proposals, recalled,
        preliminary_status, made_progress, db_path, loop_id, event_ids,
    )

    # Cap the audit list of created-memory ids so WillState (and thus every snapshot)
    # does not grow without bound over a long run. It is an audit trail, never iterated
    # for correctness — the memory store is the source of truth; recent ids suffice.
    if len(state.memory_ids) > MEMORY_IDS_CAP:
        state.memory_ids = state.memory_ids[-MEMORY_IDS_CAP:]

    create_snapshot(state, path=db_path)

    loop = AutonomousValueLoop(
        id=loop_id,
        status=eval_event.status,
        environment=environment,
        observation_ids=[obs.id for obs in observations],
        thought_ids=[thought.id for thought in thoughts],
        drive_ids=[drive.id for drive in drives],
        intention_id=intention.id,
        plan_id=state.active_plan.id if state.active_plan else None,
        proposal_id=proposal.id,
        policy_result_id=policy.id,
        action_record_id=action_record.id if action_record else None,
        verification_result_id=verification.id if verification else None,
        reflection_id=reflection.id,
        eval_event_id=eval_event.id,
    )
    return LoopRunResult(
        loop=loop,
        event_ids=event_ids,
        proposal_id=proposal.id,
        policy_decision=policy.decision,
        action_status=action_record.status if action_record else ActionStatus.BLOCKED.value,
        verification_status=("passed" if verification and verification.passed else "failed" if verification else "not_run"),
        loop_status=eval_event.status,
    )


def _inject_authored_hypothesis(env, llm, state, arbbot_proposals, memory_store, recalled,
                                db_path, loop_id, event_ids):
    """A2.2 — authored hypothesis: when the env exposes a parameter space (`backtest_universe`),
    let the LLM AUTHOR one concrete backtest with a SELF-CHOSEN threshold (not just pick an
    enumerated index) from the universe + ledger + any standing critique note, and inject it as
    one more candidate the chooser may take. Both walls hold: the env builds the command from its
    OWN vocabulary (wall 1: authoring can only parameterize a declared sentinel) and
    run_policy_gate re-validates the params (wall 2). Returns the proposal list unchanged when
    the env has no universe (e.g. self_repo), the LLM is off, or it authors nothing."""
    if llm is None or not hasattr(env, "backtest_universe"):
        return arbbot_proposals
    universe = env.backtest_universe()
    if not universe:
        return arbbot_proposals
    author_ledger, _ = _build_frontier(memory_store, arbbot_proposals)
    spec = author_backtest(
        llm, universe, author_ledger, recalled=recalled,
        budget_balance=state.budget.balance, budget_pressure=budget_pressure(state.budget),
        on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "author"),
    )
    if spec is None:
        return arbbot_proposals
    authored = env.authored_backtest(spec)
    _append(db_path, EventType.HYPOTHESIS_AUTHORED, "action_proposal", authored.id, authored, loop_id, event_ids=event_ids)
    return [authored] + arbbot_proposals


def _judge_and_record_finding(action_record, proposal, verification, llm, memory_store, state,
                              drive_rel, db_path, loop_id, event_ids) -> bool:
    """Turn the action's real output into a durable, subject-keyed experiment-ledger finding,
    and replenish the budget only on CONCLUSIVE new knowledge. When the action produced
    structured backtest metrics, a DETERMINISTIC judgment (kill/iterate/promote/insufficient by
    fixed rules) IS the finding — the verdict, not an LLM's reading of stdout, enters the ledger,
    so a single lucky window (n_entered=1) is never recorded as an edge. Other experiment probes
    keep the LLM extraction; routine checks (git status) produce no finding. Re-running a probe
    supersedes its prior finding. Returns verified_value — whether this was structurally-settled
    new knowledge: a judge_backtest CONCLUSIVE verdict (PROMOTE/KILL) on a first-time finding.
    That ONE signal gates replenishment AND the calibration outcome AND plan progress alike. A
    non-backtest LLM-extracted finding (judgment is None) updates the ledger but is not value —
    INSUFFICIENT/ITERATE is not yet knowledge, and paying for a mere rephrasing of the same
    output would let the economy reward noise and fake plan progress."""
    judgment = judge_backtest(action_record.metrics) if action_record else None
    if judgment is not None:
        _append(
            db_path, EventType.JUDGMENT_RENDERED, "judgment", action_record.id,
            {"verdict": judgment.verdict.value, "confidence": judgment.confidence, "reasons": judgment.reasons},
            loop_id, event_ids=event_ids,
        )
        finding = judgment_finding(judgment)
    elif proposal.experiment:
        finding = extract_finding(
            llm, action_record, verification,
            on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "finding"),
        )
    else:
        finding = None
    if finding is None:
        return False
    subject = probe_subject(action_record.command) if action_record else None
    prior = next(
        (
            m.content
            for m in memory_store.backend.all(live_only=True)
            if m.subject == subject and m.kind == "arbbot:experiment" and m.valid_until is None
        ),
        None,
    )
    surprise = novelty_vs_prior(prior, finding)
    finding_memory = memory_store.remember(
        finding,
        memory_type=MemoryType.SEMANTIC,
        kind="arbbot:experiment",
        subject=subject,
        grounding=[" ".join(action_record.command)] if action_record else [],
        source=MemorySource.INFERRED,
        will_state=state,
        signals=derive_signals(finding, state, drive_relevance=drive_rel, novelty=surprise),
    )
    state.memory_ids.append(finding_memory.id)
    # Carry the surprise forward: a finding that departed from the prior belief about its subject
    # raises how strongly the NEXT loop encodes what it observes. novelty on this SEMANTIC finding
    # is largely held at the type floor; the carryover lands on the next observation (EPISODIC,
    # floor 0) where it actually moves salience (arousal enhances encoding — McGaugh).
    state.last_surprise = surprise
    # A weak-but-positive ITERATE verdict is a deferred intention, not yet knowledge: set a
    # time-triggered prospective to re-test this subject later (once more data has accrued), so
    # "tune the threshold / widen the sample" actually resurfaces instead of being said and dropped.
    if judgment is not None and judgment.verdict == Verdict.ITERATE and subject:
        retest_at = datetime.fromisoformat(utc_now_iso()) + timedelta(hours=PROSPECTIVE_RETEST_HOURS)
        prospective = memory_store.remember(
            f"re-test {subject}: widen the sample or tune the threshold (was ITERATE)",
            memory_type=MemoryType.PROSPECTIVE,
            kind="arbbot:retest",
            subject=subject,
            trigger=f"time:{retest_at.isoformat()}",
            source=MemorySource.INFERRED,
            will_state=state,
        )
        state.memory_ids.append(prospective.id)
    # `verified_value` (structured CONCLUSIVE new knowledge) is the value signal that gates
    # replenishment, calibration outcome, and plan progress alike; `cognitively_new` (textual
    # novelty) is only its precondition. A non-backtest LLM-extracted finding (judgment is None)
    # updates the ledger but is not value — it cannot farm the knowledge bonus or fake progress.
    cognitively_new = is_new_knowledge(prior, finding)
    verified_value = (
        judgment is not None and judgment.verdict in CONCLUSIVE and cognitively_new
    )
    if verified_value:
        state.budget = replenish(state.budget, KNOWLEDGE_REPLENISH)
        _append(db_path, EventType.BUDGET_REPLENISHED, "budget", state.id, state.budget, loop_id, event_ids=event_ids)
    return verified_value


def _deliberate_next_goal(llm, state, memory_store, arbbot_proposals, recalled,
                          preliminary_status, made_progress, db_path, loop_id, event_ids) -> None:
    """The loop's deliberation tail: yizhi sets its OWN next goal from the experiment ledger
    + frontier, (de)composes it into a multi-loop plan (a new goal supersedes an in-flight
    plan; a stalled plan is re-decomposed), and raises a critique of any 'no edge' result that
    may be a FALSE NEGATIVE (leaving a standing re-test note the backtest oracle later judges).
    All plan control lives here, touching only state + the event log — the LangGraph-swappable
    seam. Deterministic default: no LLM / no vision -> no goal, no plan, no critique."""
    if llm is None or not state.vision:
        return
    ledger, frontier = _build_frontier(memory_store, arbbot_proposals)

    # Goal lifecycle (deterministic): retire the current goal BEFORE deciding whether to set a new
    # one, so a goal is pursued to completion instead of overwritten every loop. Its plan running
    # to COMPLETED is DONE; a plan that keeps stalling past MAX_PLAN_REVISIONS is ABANDONED; a
    # single-step goal (no plan) that produced verified value this loop is DONE.
    cur = state.goals[0] if state.goals else None
    plan = state.active_plan
    if cur is not None and cur.status == GoalStatus.PURSUING:
        same_plan = plan is not None and plan.goal_id == cur.id
        if same_plan and plan.status == PlanStatus.COMPLETED:
            cur.status = GoalStatus.DONE
        elif same_plan and plan.status == PlanStatus.ACTIVE and plan.stall_count >= STALL_BUDGET and plan.revision >= MAX_PLAN_REVISIONS:
            cur.status = GoalStatus.ABANDONED
        elif plan is None and made_progress:
            cur.status = GoalStatus.DONE
        if cur.status != GoalStatus.PURSUING:
            _append(db_path, EventType.GOAL_RETIRED, "goal", cur.id,
                    {"goal_id": cur.id, "status": cur.status.value}, loop_id, event_ids=event_ids)

    # Genesis is conditional: set a new goal ONLY when there is none or the current one was just
    # retired. While the current goal is PURSUING, keep it and let its Plan run across loops — this
    # single branch is what makes "persistently advance one task" possible (it was an unconditional
    # overwrite, which stale-killed every in-flight plan via the goal_id check in run_step).
    needs_new_goal = cur is None or cur.status != GoalStatus.PURSUING
    if needs_new_goal:
        new_goal = generate_goal(
            llm, state.vision, cur, ledger,
            state.budget.balance, budget_pressure(state.budget),
            frontier=frontier, recalled=recalled,
            on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "goal"),
        )
        if new_goal is not None:
            state.goals = [new_goal]
            _append(db_path, EventType.GOAL_SET, "goal", new_goal.id, new_goal, loop_id, event_ids=event_ids)
            fresh = decompose_goal(
                llm, new_goal, arbbot_proposals, frontier,
                state.budget.balance, budget_pressure(state.budget),
                max_steps=_plan_depth(state.budget), recalled=recalled,
                on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "decompose"),
            )
            state.active_plan = fresh   # None => single-step (unchanged behavior)
            if fresh is not None:
                _append(db_path, EventType.PLAN_CREATED, "plan", fresh.id, fresh, loop_id, event_ids=event_ids)
        # new_goal None while needing one: leave the slot retired; next loop retries genesis.
    elif plan is not None and plan.status == PlanStatus.ACTIVE and plan.stall_count >= STALL_BUDGET:
        # current goal still PURSUING but its plan stalled out: re-decompose (never overwrite the goal)
        replan = decompose_goal(
            llm, cur, arbbot_proposals, frontier,
            state.budget.balance, budget_pressure(state.budget),
            max_steps=_plan_depth(state.budget),
            failure_context=f"stalled {plan.stall_count} loops; last status {getattr(preliminary_status, 'value', preliminary_status)}",
            recalled=recalled,
            on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "replan"),
        )
        if replan is not None:
            replan.revision = plan.revision + 1
            state.active_plan = replan
            _append(db_path, EventType.PLAN_REPLANNED, "plan", replan.id, replan, loop_id, event_ids=event_ids)
        else:
            state.active_plan = None

    # Critique faculty: question a 'no edge' result that may be a FALSE NEGATIVE and leave a
    # high-salience standing self-note to RE-TEST it (a filtered backtest). yizhi does NOT
    # decide truth here — the deterministic backtest oracle does, on a later loop.
    critique = generate_critique(llm, ledger, on_fallback=_llm_fallback_sink(db_path, loop_id, event_ids, "critique"))
    if critique is not None:
        _append(db_path, EventType.CRITIQUE_RAISED, "critique", loop_id, critique, loop_id, event_ids=event_ids)
        note = critique_memory(critique)
        crit_mem = memory_store.remember(
            note, memory_type=MemoryType.REFLECTIVE, kind="self:critique", subject="self/critique",
            will_state=state, signals=derive_signals(note, state, novelty=1.0, stake_relevance=1.0), source=MemorySource.INFERRED,
        )
        state.memory_ids.append(crit_mem.id)


def _preliminary_status(
    policy: PolicyGateResult,
    action: ActionRecord | None,
    verification: VerificationResult | None,
    budget_halted: bool = False,
) -> LoopStatus:
    if not policy.allowed or budget_halted:
        return LoopStatus.BLOCKED
    if action and action.status == ActionStatus.FAILED:
        return LoopStatus.FAILED
    if verification and not verification.passed:
        return LoopStatus.FAILED
    if verification and verification.passed:
        return LoopStatus.FULL
    return LoopStatus.PARTIAL


def _plan_depth(budget) -> int:
    """Budget-gated plan length: shallower plans under existence pressure, none when
    near halt (don't over-commit a multi-step plan when survival is threatened)."""
    p = budget_pressure(budget)
    if p >= 0.66:
        return 0   # too close to halt -> no multi-step plan; single-step only
    if p >= 0.33:
        return 2
    return 4


def _build_frontier(memory_store, proposals):
    """The experiment ledger (current findings by subject) and the frontier — each
    available action tagged with whether it is already established. Shared by goal-
    genesis and plan (de)composition so both see one consistent view of the unknown."""
    current = {
        (m.subject or ""): m.content
        for m in memory_store.backend.all(live_only=True)
        if m.kind == "arbbot:experiment" and m.valid_until is None
    }
    ledger = [(subject, content) for subject, content in current.items() if subject]
    frontier = [
        (p.title, current.get(probe_subject(p.command)), bool(p.experiment))
        for p in proposals
    ]
    return ledger, frontier
