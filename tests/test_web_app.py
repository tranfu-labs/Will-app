"""Web panel HTTP layer (yizhi/web/app.py + yizhi/web/data.py).

Pins the panel's contract: read-only pages/API over a real event store, the SSE
first packet, and the single write seam — an approval POST appends a JSON line
to the channel inbox that `LocalInboxChannel.poll()` round-trips, without ever
touching the inbox cursor. Skipped wholesale when the optional [web] extra is
not installed; the core suite stays green without fastapi.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from yizhi.channels.base import InboundVerb  # noqa: E402
from yizhi.channels.local_inbox import LocalInboxChannel  # noqa: E402
from yizhi.core.schemas import (  # noqa: E402
    ActionClass,
    ActionProposal,
    EnvironmentName,
    EventType,
    ExistenceBudget,
    Goal,
    Intention,
    Plan,
    PlanStep,
    PlanStepStatus,
    WillState,
)
from yizhi.state.store import append_event, create_snapshot, init_db  # noqa: E402
from yizhi.web.app import create_app  # noqa: E402
from yizhi.web.data import fetch_events, max_event_rowid  # noqa: E402


@pytest.fixture()
def panel(tmp_path):
    db = tmp_path / "state.sqlite"
    channel_root = tmp_path / "channel"
    packet = tmp_path / "packet.json"
    init_db(db)

    goal = Goal(title="Find a funding edge", description="walk the deterministic queue")
    append_event(EventType.GOAL_SET, "goal", goal.id, goal, path=db)
    append_event(
        EventType.INTENTION_ACTIVATED, "intention", "int-1",
        Intention(title="Probe the queue", rationale="evidence replenishes", endorsed_drive="curiosity_gap"),
        path=db,
    )
    proposal = ActionProposal(
        environment=EnvironmentName.SELF_REPO,
        action_class=ActionClass.INTERNAL,
        title="apply patch to fundarb",
        requires_approval=True,
    )
    append_event(EventType.ACTION_PROPOSED, "action", proposal.id, proposal, correlation_id="corr-approve-1", path=db)
    append_event(
        EventType.JUDGMENT_RENDERED, "judgment", "act-1",
        {"verdict": "KILL", "confidence": 0.9, "reasons": ["negative pnl"]},
        correlation_id="corr-loop-1", path=db,
    )
    state = WillState(
        vision="verified funding-diff knowledge",
        goals=[goal],
        active_plan=Plan(
            goal_id=goal.id,
            cursor=1,
            steps=[
                PlanStep(description="build dataset", status=PlanStepStatus.DONE),
                PlanStep(description="run backtests", status=PlanStepStatus.ACTIVE),
            ],
        ),
        budget=ExistenceBudget(balance=40.0, initial=100.0),
        loop_count=3,
    )
    create_snapshot(state, path=db)
    packet.write_text(json.dumps({
        "generated_at": "2026-07-01T00:00:00+00:00",
        "summary": {"decisions": 1, "kill": 1, "insufficient": 0, "iterate": 0, "promote": 0},
        "safety": {"live_trading_authorized": False},
        "decisions": [{"symbol": "BTCUSDT", "decision": "kill_or_data_requirement",
                       "judgment": "KILL", "reason": "enter-all baseline loses", "next_action": "collect data"}],
    }))

    app = create_app(db_path=db, channel_root=channel_root, packet_path=packet, poll_interval=0.01)
    return TestClient(app), db, channel_root


def test_all_pages_render(panel):
    client, _, _ = panel
    for path, marker in [
        ("/", "当前目标"),
        ("/tasks", "任务历史"),
        ("/timeline", "事件流"),
        ("/deliverables", "promotion packet"),
        ("/approvals", "审批队列"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert marker in response.text, path


def test_api_state_projects_snapshot(panel):
    client, _, _ = panel
    state = client.get("/api/state").json()
    assert state["has_state"] is True
    assert state["goal_title"] == "Find a funding edge"
    assert (state["plan_cursor"], state["plan_total"]) == (1, 2)
    assert state["intention_title"] == "Probe the queue"
    assert state["budget_pct"] == 40


def test_api_tasks_returns_goal_history(panel):
    client, _, _ = panel
    tasks = client.get("/api/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Find a funding edge"
    assert tasks[0]["status"] == "pursuing"
    assert tasks[0]["verdicts"] == ["KILL"]
    assert (tasks[0]["steps_total"], tasks[0]["steps_done"]) == (2, 1)


def test_api_events_type_filter(panel):
    client, _, _ = panel
    all_events = client.get("/api/events").json()
    only_judgments = client.get("/api/events", params={"type": EventType.JUDGMENT_RENDERED.value}).json()
    assert len(all_events) > len(only_judgments) >= 1
    assert all(e["type"] == EventType.JUDGMENT_RENDERED.value for e in only_judgments)
    assert "KILL" in only_judgments[0]["summary"]


def test_approval_post_round_trips_through_inbox(panel):
    client, _, channel_root = panel
    pending = client.get("/api/approvals").json()
    assert pending and pending[0]["status"] == "pending"
    cid = pending[0]["correlation_id"]

    response = client.post(f"/api/approvals/{cid}", json={"verb": "approve"})
    assert response.status_code == 200 and response.json()["status"] == "submitted"

    # the panel wrote a line the will loop's channel round-trips...
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [(InboundVerb.APPROVE, cid)]
    # ...and the panel itself never advanced the loop's cursor
    assert not (channel_root / ".inbox_cursor").exists() or commands

    after = client.get("/api/approvals").json()
    assert after[0]["status"] == "submitted"


def test_approval_post_unknown_cid_is_404(panel):
    client, _, _ = panel
    assert client.post("/api/approvals/corr-nope", json={"verb": "approve"}).status_code == 404


def test_approval_post_rejects_unknown_verb(panel):
    client, _, _ = panel
    assert client.post("/api/approvals/corr-approve-1", json={"verb": "launch"}).status_code == 422


def test_api_deliverables_serves_packet(panel):
    client, _, _ = panel
    body = client.get("/api/deliverables").json()
    assert body["packet"]["summary"]["kill"] == 1
    assert body["budget_series"] and body["budget_series"][0][1] == 40.0


def test_sse_first_packet_is_full_state(panel):
    client, _, _ = panel
    response = client.get("/stream", params={"max_cycles": 0})
    assert response.status_code == 200
    assert response.text.startswith("event: state\n")
    payload = json.loads(response.text.split("data: ", 1)[1].split("\n", 1)[0])
    assert payload["goal_title"] == "Find a funding edge"


def test_event_rowid_cursor_semantics(panel):
    _, db, _ = panel
    top = max_event_rowid(db)
    append_event(EventType.THOUGHT_EVENT_GENERATED, "thought", "th-1", {"content": "new"}, path=db)
    fresh = fetch_events(db, after_rowid=top)
    assert len(fresh) == 1 and fresh[0]["type"] == EventType.THOUGHT_EVENT_GENERATED.value


def test_chat_send_and_timeline_round_trip(panel):
    client, _, channel_root = panel
    assert client.get("/chat").status_code == 200

    response = client.post("/api/chat", json={"verb": "ask", "text": "进展如何？"})
    assert response.status_code == 200
    # the message is now a poll-able inbound command for the will loop...
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [(InboundVerb.ASK, "进展如何？")]
    # ...and shows up in the conversation timeline as a human message
    timeline = client.get("/api/chat").json()
    assert any(m["role"] == "human" and m["text"] == "进展如何？" for m in timeline)
    assert timeline[-1]["role"] == "agent" and timeline[-1]["label"] == "submitted"


def test_chat_auto_status_replies_without_writing_inbox(panel):
    client, _, channel_root = panel
    response = client.post("/api/chat", json={"verb": "auto", "text": "现在进展如何？"})
    assert response.status_code == 200
    assert not (channel_root / "inbox.jsonl").exists()
    timeline = client.get("/api/chat").json()
    assert timeline[-1]["label"] == "status"
    assert "Find a funding edge" in timeline[-1]["text"]


def test_chat_confirm_card_gates_kill_goal(panel):
    client, _, channel_root = panel
    response = client.post("/api/chat", json={"verb": "kill", "text": "goal"})
    assert response.status_code == 200
    assert not (channel_root / "inbox.jsonl").exists()
    timeline = client.get("/api/chat").json()
    pending = timeline[-1]["pending_action"]
    assert pending and pending["verb"] == "kill"

    confirmed = client.post(f"/api/chat/confirm/{pending['id']}")
    assert confirmed.status_code == 200
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [(InboundVerb.KILL, "goal")]


def test_chat_agent_replies_render_in_timeline(panel):
    client, _, channel_root = panel
    from yizhi.channels.base import OutboundMessage
    LocalInboxChannel(channel_root).send(OutboundMessage(title="回复：进展如何？", body="预算 40，回路 3。"))
    timeline = client.get("/api/chat").json()
    agent_msgs = [m for m in timeline if m["role"] == "agent"]
    assert agent_msgs and agent_msgs[-1]["title"] == "回复：进展如何？"


def test_chat_rejects_empty_and_non_goal_kill(panel):
    client, _, _ = panel
    assert client.post("/api/chat", json={"verb": "note", "text": "   "}).status_code == 422
    assert client.post("/api/chat", json={"verb": "kill", "text": "corr-123"}).status_code == 422
    assert client.post("/api/chat", json={"verb": "launch", "text": "x"}).status_code == 422
    assert client.post("/api/chat", json={"verb": "kill", "text": "goal"}).status_code == 200


def test_missing_db_yields_empty_panel(tmp_path):
    app = create_app(db_path=tmp_path / "absent.sqlite", channel_root=tmp_path / "ch", packet_path=tmp_path / "no.json")
    client = TestClient(app)
    assert client.get("/api/state").json()["has_state"] is False
    assert client.get("/api/tasks").json() == []
    assert client.get("/").status_code == 200
    assert (tmp_path / "absent.sqlite").exists() is False  # read-only: the panel never creates the store
