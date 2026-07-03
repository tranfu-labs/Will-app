from __future__ import annotations

import json

import pytest

from yizhi.channels.base import InboundVerb
from yizhi.channels.local_inbox import LocalInboxChannel
from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName, EventType, Goal, WillState
from yizhi.liaison.tools import LiaisonTools
from yizhi.state.store import append_event, create_snapshot, init_db


@pytest.fixture()
def liaison_fixture(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    channel_root = tmp_path / "channel"
    packet = tmp_path / "packet.json"
    goal = Goal(title="Find a funding edge")
    append_event(EventType.GOAL_SET, "goal", goal.id, goal, path=db)
    append_event(EventType.JUDGMENT_RENDERED, "judgment", "j1", {"verdict": "KILL", "subject": "BTC"}, path=db)
    append_event(EventType.DELEGATION_COMPLETED, "delegation", "d1", {"summary": "repo inspected"}, path=db)
    append_event(
        EventType.ACTION_PROPOSED,
        "action",
        "a1",
        ActionProposal(
            environment=EnvironmentName.SELF_REPO,
            action_class=ActionClass.EXTERNAL_WRITE,
            title="push branch",
            requires_approval=True,
        ),
        correlation_id="corr-approve-1",
        path=db,
    )
    create_snapshot(WillState(goals=[goal], loop_count=2), path=db)
    packet.write_text(json.dumps({"summary": {"decisions": 1}}), encoding="utf-8")
    return LiaisonTools(db_path=db, channel_root=channel_root, packet_path=packet), channel_root


def test_read_tools_project_existing_state(liaison_fixture):
    tools, _ = liaison_fixture
    assert tools.get_state()["goal_title"] == "Find a funding edge"
    assert tools.get_tasks()[0]["title"] == "Find a funding edge"
    assert tools.get_findings()[0]["verdict"] == "KILL"
    assert tools.get_packet()["summary"]["decisions"] == 1
    assert tools.get_delegations()[0]["payload"]["summary"] == "repo inspected"


def test_send_to_will_direct_and_confirmation_gated(liaison_fixture):
    tools, channel_root = liaison_fixture
    note = tools.send_to_will("note", "fees matter")
    ask = tools.send_to_will("ask", "进展如何？")
    assert note.verb == InboundVerb.NOTE and ask.verb == InboundVerb.ASK

    with pytest.raises(PermissionError):
        tools.send_to_will("vision", "new vision")
    with pytest.raises(PermissionError):
        tools.send_to_will("kill", "goal")
    with pytest.raises(PermissionError):
        tools.send_to_will("approve", "corr-approve-1")

    tools.send_to_will("vision", "new vision", confirmed=True)
    tools.send_to_will("kill", "goal", confirmed=True)
    tools.send_to_will("approve", "corr-approve-1", confirmed=True)
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [
        (InboundVerb.NOTE, "fees matter"),
        (InboundVerb.ASK, "进展如何？"),
        (InboundVerb.VISION, "new vision"),
        (InboundVerb.KILL, "goal"),
        (InboundVerb.APPROVE, "corr-approve-1"),
    ]


def test_approve_requires_real_pending_correlation(liaison_fixture):
    tools, _ = liaison_fixture
    with pytest.raises(ValueError):
        tools.send_to_will("approve", "corr-nope", confirmed=True)
