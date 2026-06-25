from pathlib import Path

import pytest

from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName, WillState
from yizhi.engine.loop import run_step
from yizhi.environments.arbbot import ArbBotEnvironment
from yizhi.eval.loops import list_loop_evals
from yizhi.state.store import list_events


ARBBOT_ROOT = Path("/Users/griffith/Projects/AI/ArbBot")


class DeniedArbBotEnvironment(ArbBotEnvironment):
    def propose_actions(self, state: WillState):
        return [
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.FINANCIAL,
                title="bad live command",
                command=["python", "trade.py", "--live", "place_order"],
                dry_run=False,
            )
        ]


def test_self_loop_generates_full_or_partial(tmp_path):
    from yizhi.environments.self_repo import SelfRepoEnvironment

    db = tmp_path / "state.sqlite"
    result = run_step(SelfRepoEnvironment(), WillState(), db)
    assert result.proposal_id is not None
    assert result.policy_decision == "allow"
    assert result.loop_status in {"full", "partial", "failed"}
    events = list_events(correlation_id=result.loop.id, path=db)
    event_types = {event["type"] for event in events}
    assert "ObservationRecorded" in event_types
    assert "ThoughtEventGenerated" in event_types
    assert "IntentionActivated" in event_types
    assert "EvalEventRecorded" in event_types


def test_arbbot_denied_loop_records_eval_event(tmp_path):
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    db = tmp_path / "state.sqlite"
    result = run_step(DeniedArbBotEnvironment(ARBBOT_ROOT), WillState(), db)
    assert result.policy_decision == "deny"
    assert result.action_status == "blocked"
    assert result.loop_status == "blocked"
    events = list_events(correlation_id=result.loop.id, path=db)
    event_types = {event["type"] for event in events}
    assert "PolicyGateDenied" in event_types
    assert "EvalEventRecorded" in event_types
    assert list_loop_evals(db)


def test_arbbot_loop_status_observation_only_safe(tmp_path):
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    db = tmp_path / "state.sqlite"
    before = (ARBBOT_ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    result = run_step(ArbBotEnvironment(ARBBOT_ROOT), WillState(), db)
    after = (ARBBOT_ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    assert before == after
    assert result.policy_decision == "allow"
    assert result.action_status in {"succeeded", "failed"}
