from __future__ import annotations

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.store import load_campaign, save_campaign_started
from yizhi.core.schemas import ActionStatus, EnvironmentName, EventType, WillState
from yizhi.engine.loop import environment_from_name, run_step
from yizhi.environments.campaign import CampaignEnvironment
from yizhi.policy.gates import run_policy_gate
from yizhi.state.store import init_db, list_events


def _campaign(tmp_path, cid="btc-env"):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id=cid, workspace_root=tmp_path / "ws")
    save_campaign_started(db, campaign)
    return db, campaign


def test_observe_reports_campaign_state(tmp_path):
    db, _ = _campaign(tmp_path)
    env = CampaignEnvironment(db, "btc-env")

    observations = env.observe()

    facts = observations[0].facts
    assert facts["exists"] is True
    assert facts["cursor"] == 0
    assert facts["active_stage_id"] == "S1"

    missing = CampaignEnvironment(db, "no-such").observe()
    assert missing[0].facts["exists"] is False


def test_proposals_pass_the_policy_gate(tmp_path):
    db, _ = _campaign(tmp_path)
    env = CampaignEnvironment(db, "btc-env")

    proposals = env.propose_actions(WillState())

    kinds = [p.metadata["campaign_op"]["op"] for p in proposals]
    assert kinds == ["tick", "report"]           # active campaign, nothing rejected
    assert proposals[0].experiment               # a tick produces deliverable evidence
    for proposal in proposals:
        assert run_policy_gate(proposal).allowed, proposal.title


def test_gate_denies_revisit_without_evidence(tmp_path):
    db, _ = _campaign(tmp_path)
    env = CampaignEnvironment(db, "btc-env")
    bad = env._proposal(
        "revisit",
        title="whimsical rework",
        description="no evidence attached",
        extra={"stage_id": "S1", "note": "想重做"},
    )

    gate = run_policy_gate(bad)

    assert not gate.allowed
    assert any("evidence" in reason for reason in gate.reasons)


def test_tick_through_run_step_advances_campaign_and_leaves_memory(tmp_path):
    db, campaign = _campaign(tmp_path)
    state = WillState()
    env = environment_from_name("campaign", db_path=db, campaign_id="btc-env", state=state)

    result = run_step(env, state, db)

    assert result.action_status == ActionStatus.SUCCEEDED.value
    reloaded = load_campaign(db, "btc-env")
    assert reloaded.cursor == 1                   # S1 accepted, will advanced the campaign
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.DELIVERABLE_ACCEPTED.value in event_types
    assert EventType.MEMORY_CREATED.value in event_types    # the tick left episodic memory


def test_rejected_stage_makes_revisit_ride_first(tmp_path):
    db, campaign = _campaign(tmp_path)
    campaign.stages[0].status = "rejected"
    campaign.stages[0].deliverable_id = "deliverable-x"
    env = CampaignEnvironment(db, "btc-env")
    env._load = lambda: campaign                  # inject the rejected in-memory state

    proposals = env.propose_actions(WillState())

    ops = [p.metadata["campaign_op"]["op"] for p in proposals]
    assert ops[0] == "revisit"
    assert proposals[0].metadata["campaign_op"]["evidence"] == "deliverable-x"
    assert run_policy_gate(proposals[0]).allowed


def test_run_rejects_mismatched_campaign_id(tmp_path):
    db, _ = _campaign(tmp_path)
    env = CampaignEnvironment(db, "btc-env")
    forged = env._proposal("tick", title="forged", description="wrong id")
    forged.metadata["campaign_op"]["campaign_id"] = "other-campaign"

    record = env.run(forged)

    assert record.status == ActionStatus.FAILED
    assert "does not match" in (record.error or "")
    assert not env.verify(record).passed
