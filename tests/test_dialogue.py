"""Dialogue seam tests: human words reach the will, governance commands apply
with events, asks get answered, and the runner drains a real channel offline.

Everything runs deterministic (conftest forces the LLM off); the LLM answer path
is exercised with a fake client. This pins the R2 exit criterion that was open
until now: channel commands actually enter the next loop as observations.
"""

from __future__ import annotations

import json

from yizhi.channels.base import InboundCommand, InboundVerb
from yizhi.channels.local_inbox import LocalInboxChannel
from yizhi.core.schemas import EventType, ExistenceBudget, Goal, GoalStatus, WillState
from yizhi.engine.dialogue import (
    INBOUND_SALIENCE,
    answer_asks,
    apply_governance,
    inbound_observations,
    is_kill_goal,
)
from yizhi.engine.runner import run_until
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.state.snapshots import load_or_create_state
from yizhi.state.store import init_db, list_events


def _cmd(verb: InboundVerb, arg: str = "") -> InboundCommand:
    return InboundCommand(verb=verb, arg=arg, raw=f"{verb.value} {arg}".strip())


# ---- apply_governance ----

def test_vision_command_reseeds_vision_with_event(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    state = WillState()
    msgs = apply_governance(state, [_cmd(InboundVerb.VISION, "find a real funding edge")], db)
    assert state.vision == "find a real funding edge"
    events = list_events(event_type=EventType.VISION_SET.value, path=db)
    assert len(events) == 1 and events[0]["payload"]["vision"] == state.vision
    assert msgs and "愿景" in msgs[0].title


def test_kill_goal_abandons_pursuing_goal_with_event(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    state = WillState(goals=[Goal(title="stale direction")])
    msgs = apply_governance(state, [_cmd(InboundVerb.KILL, "goal")], db)
    assert state.goals[0].status == GoalStatus.ABANDONED
    events = list_events(event_type=EventType.GOAL_RETIRED.value, path=db)
    assert len(events) == 1 and events[0]["payload"]["reason"] == "human_kill"
    assert msgs and "放弃" in msgs[0].title


def test_kill_goal_without_pursuing_goal_reports_no_op(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    state = WillState(goals=[])
    msgs = apply_governance(state, [_cmd(InboundVerb.KILL, "goal")], db)
    assert msgs and "没有" in msgs[0].title
    assert list_events(event_type=EventType.GOAL_RETIRED.value, path=db) == []


def test_kill_with_correlation_arg_is_approval_not_goal_kill(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    state = WillState(goals=[Goal(title="keep me")])
    command = _cmd(InboundVerb.KILL, "corr-123")
    assert not is_kill_goal(command)
    assert apply_governance(state, [command], db) == []
    assert state.goals[0].status == GoalStatus.PURSUING


# ---- inbound_observations ----

def test_utterances_become_high_salience_observations():
    commands = [
        _cmd(InboundVerb.NOTE, "watch fee assumptions"),
        _cmd(InboundVerb.ASK, "何时能有结论？"),
        _cmd(InboundVerb.VISION, "applied elsewhere"),   # governance: not re-perceived
        _cmd(InboundVerb.KILL, "goal"),                  # governance: not re-perceived
        _cmd(InboundVerb.KILL, "corr-9"),                # approval signal: perceived
    ]
    observations = inbound_observations(commands, "self_repo")
    assert [o.facts["verb"] for o in observations] == ["note", "ask", "kill"]
    assert all(o.salience == INBOUND_SALIENCE for o in observations)
    assert all(o.source == "channel_inbox" for o in observations)
    assert "watch fee assumptions" in observations[0].summary


# ---- answer_asks ----

def test_ask_answered_with_deterministic_receipt():
    state = WillState(vision="edge hunting", budget=ExistenceBudget(balance=42.0), loop_count=5)
    replies = answer_asks(state, [_cmd(InboundVerb.ASK, "现在进展如何？")])
    assert len(replies) == 1
    body = replies[0].body
    assert "42.0" in body and "5" in body and "edge hunting" in body
    assert replies[0].title.startswith("回复")


def test_ask_answered_by_llm_with_fallback_to_receipt():
    class FakeLLM:
        def complete_json(self, system, prompt):
            assert "question" in prompt
            return {"answer": "当前证据不足，先补数据。"}

    class BoomLLM:
        def complete_json(self, system, prompt):
            raise RuntimeError("provider down")

    state = WillState()
    good = answer_asks(state, [_cmd(InboundVerb.ASK, "该上钱吗？")], llm=FakeLLM())
    assert good[0].body == "当前证据不足，先补数据。"
    degraded = answer_asks(state, [_cmd(InboundVerb.ASK, "该上钱吗？")], llm=BoomLLM())
    assert "存续预算" in degraded[0].body  # the receipt, not a dropped reply


def test_non_ask_commands_get_no_reply():
    assert answer_asks(WillState(), [_cmd(InboundVerb.NOTE, "fyi")]) == []


# ---- runner integration (offline, deterministic) ----

def test_run_until_drains_channel_round_trip(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    channel = LocalInboxChannel(tmp_path / "ch")
    (tmp_path / "ch").mkdir()
    (tmp_path / "ch" / "inbox.jsonl").write_text(
        "vision verified funding-diff knowledge\n"
        "note fees matter more than spread\n"
        "ask 当前状态如何？\n",
        encoding="utf-8",
    )
    state = load_or_create_state(db)
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=1, stop_on_stuck=False, channel=channel)
    assert outcome.steps == 1

    # governance applied before the step, with its event
    assert state.vision == "verified funding-diff knowledge"
    assert list_events(event_type=EventType.VISION_SET.value, path=db)

    # the note entered the loop as a high-salience observation event
    observations = list_events(event_type=EventType.OBSERVATION_RECORDED.value, path=db)
    human = [o for o in observations if o["payload"].get("source") == "channel_inbox"]
    assert any("fees matter" in o["payload"]["summary"] for o in human)

    # the ask got an answer in the outbox (vision confirmation + reply)
    outbox = [json.loads(line) for line in (tmp_path / "ch" / "outbox.jsonl").read_text().splitlines()]
    titles = [m["title"] for m in outbox]
    assert any("愿景" in t for t in titles) and any(t.startswith("回复") for t in titles)
    reply = next(m for m in outbox if m["title"].startswith("回复"))
    assert "verified funding-diff knowledge" in reply["body"]  # answered from post-step state


def test_run_until_without_channel_is_unchanged(tmp_path):
    db = init_db(tmp_path / "db.sqlite")
    state = load_or_create_state(db)
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=1, stop_on_stuck=False)
    assert outcome.steps == 1


def test_pending_human_input_suspends_stuck_halt(tmp_path):
    """A stuck pattern must not deafen the will: with a pending inbox message the
    step runs (digesting the words) instead of halting before the drain."""
    db = init_db(tmp_path / "db.sqlite")
    state = load_or_create_state(db)
    # Build a genuine stuck history first (repeating deterministic action).
    run_until(SelfRepoEnvironment(), state, db, max_steps=8, stuck_window=4)
    channel = LocalInboxChannel(tmp_path / "ch")
    (tmp_path / "ch").mkdir()
    (tmp_path / "ch" / "inbox.jsonl").write_text("ask 卡住了吗？\n", encoding="utf-8")
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=1, stuck_window=4, channel=channel)
    assert outcome.steps == 1  # the message was heard, not starved by the stuck halt
    outbox = (tmp_path / "ch" / "outbox.jsonl").read_text()
    assert "回复" in outbox
    # and with the inbox now empty, the stuck halt is back in force
    followup = run_until(SelfRepoEnvironment(), state, db, max_steps=5, stuck_window=4, channel=channel)
    assert followup.steps == 0 and followup.stop_reason.startswith("stuck:")
