from __future__ import annotations

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.store import load_campaign, save_campaign_started
from yizhi.core.schemas import EventType, WillState
from yizhi.engine.budget import KNOWLEDGE_REPLENISH
from yizhi.engine.loop import CAMPAIGN_ACCEPT_REPLENISH, environment_from_name, run_step
from yizhi.state.store import init_db, list_events, load_latest_snapshot


def _adopted(tmp_path, cid="btc-b2", capsys=None):
    from yizhi.cli import main

    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id=cid, workspace_root=tmp_path / "ws")
    save_campaign_started(db, campaign)
    assert main(["--db", str(db), "campaign", "adopt", "--id", cid]) == 0
    return db


def test_adopt_binds_goal_and_projects_plan(tmp_path, capsys):
    db = _adopted(tmp_path, capsys=capsys)

    state = load_latest_snapshot(db)
    goal = state.goals[0]
    assert goal.metadata["campaign_id"] == "btc-b2"
    assert state.active_plan is not None
    assert len(state.active_plan.steps) == 4                      # one step per stage
    assert state.active_plan.goal_id == goal.id
    assert state.active_plan.steps[0].target_command == ["yizhi:campaign", "tick", "btc-b2"]
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.GOAL_SET.value in event_types
    assert EventType.PLAN_CREATED.value in event_types


def test_campaign_tick_replenishes_at_reduced_tier(tmp_path, capsys):
    db = _adopted(tmp_path, capsys=capsys)
    state = load_latest_snapshot(db)
    env = environment_from_name("campaign", db_path=db, campaign_id="btc-b2", state=state)
    before = state.budget.balance

    result = run_step(env, state, db)

    assert result.action_status == "succeeded"
    # Spent the INTERNAL action cost, earned back the reduced campaign tier — and
    # the reduced tier must stay strictly below full quant-knowledge replenishment.
    assert CAMPAIGN_ACCEPT_REPLENISH < KNOWLEDGE_REPLENISH
    replenished = [e for e in list_events(path=db) if e["type"] == EventType.BUDGET_REPLENISHED.value]
    assert replenished, "acceptance should replenish the existence budget"
    assert state.budget.balance != before


def test_campaign_conclusion_enters_the_memory_ledger(tmp_path, capsys):
    db = _adopted(tmp_path, capsys=capsys)
    state = load_latest_snapshot(db)
    env = environment_from_name("campaign", db_path=db, campaign_id="btc-b2", state=state)

    run_step(env, state, db)

    memories = [e for e in list_events(path=db) if e["type"] == EventType.MEMORY_CREATED.value]
    ledger = [
        e for e in memories
        if e["payload"].get("kind") == "campaign:deliverable"
    ]
    assert ledger, "the accepted deliverable must land in the memory ledger"
    entry = ledger[0]["payload"]
    assert entry["subject"] == "campaign:btc-b2:S1"
    assert "deliverable accepted" in entry["content"]


def test_will_loop_drives_campaign_to_completion(tmp_path, capsys):
    db = _adopted(tmp_path, capsys=capsys)
    state = load_latest_snapshot(db)
    env = environment_from_name("campaign", db_path=db, campaign_id="btc-b2", state=state)

    for _ in range(4):
        run_step(env, state, db)

    campaign = load_campaign(db, "btc-b2")
    assert campaign.cursor == 4
    assert str(campaign.status) == "completed"
    # Four distinct stage conclusions in the ledger, not one overwritten row.
    memories = [
        e["payload"]["subject"]
        for e in list_events(path=db)
        if e["type"] == EventType.MEMORY_CREATED.value
        and e["payload"].get("kind") == "campaign:deliverable"
    ]
    assert {f"campaign:btc-b2:S{n}" for n in (1, 2, 3, 4)} <= set(memories)
