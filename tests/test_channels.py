"""R2 single-channel interaction layer (offline; Telegram stays manual-gated).

Pins the channel contract (file-backed send/poll), the event→message mapping (which
semantic events are worth reporting), and that reporting is infrastructure-level.
See docs/resident-operator-plan.md (pillar B, R2).
"""

from __future__ import annotations

import json

from yizhi.channels.base import InboundCommand, InboundVerb, MessageKind, OutboundMessage
from yizhi.channels.local_inbox import LocalInboxChannel
from yizhi.channels.notify import event_to_message, make_channel
from yizhi.config import ChannelConfig
from yizhi.core.schemas import EventType


# --- LocalInboxChannel: file-backed send/poll ---

def test_local_inbox_send_appends(tmp_path):
    ch = LocalInboxChannel(tmp_path)
    ch.send(OutboundMessage(title="hello", body="world"))
    ch.send(OutboundMessage(title="again"))
    lines = (tmp_path / "outbox.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["title"] == "hello"


def test_local_inbox_poll_returns_new_only(tmp_path):
    ch = LocalInboxChannel(tmp_path)
    (tmp_path / "inbox.jsonl").write_text("approve abc\nkill\n")
    first = ch.poll()
    assert [c.verb for c in first] == [InboundVerb.APPROVE, InboundVerb.KILL]
    assert first[0].arg == "abc"
    assert ch.poll() == []  # cursor advanced -> nothing new


def test_local_inbox_parses_json_line(tmp_path):
    ch = LocalInboxChannel(tmp_path)
    cmd = InboundCommand(verb=InboundVerb.ASK, arg="why kill BTC?")
    (tmp_path / "inbox.jsonl").write_text(cmd.model_dump_json() + "\n")
    got = ch.poll()
    assert got[0].verb == InboundVerb.ASK and got[0].arg == "why kill BTC?"


def test_unknown_inbound_becomes_note(tmp_path):
    ch = LocalInboxChannel(tmp_path)
    (tmp_path / "inbox.jsonl").write_text("hey what is up\n")
    got = ch.poll()
    assert got[0].verb == InboundVerb.NOTE and "hey" in got[0].arg


# --- event → message mapping ---

def test_judgment_event_is_reportable():
    event = {"type": EventType.JUDGMENT_RENDERED.value, "payload": {"verdict": "KILL", "subject": "BTC"}, "correlation_id": "loop1"}
    msg = event_to_message(event)
    assert msg is not None and msg.kind == MessageKind.REPORT
    assert "KILL" in msg.body


def test_budget_halted_is_alert():
    event = {"type": EventType.BUDGET_HALTED.value, "payload": {"reason": "depleted"}, "correlation_id": None}
    msg = event_to_message(event)
    assert msg is not None and msg.kind == MessageKind.ALERT


def test_approval_request_for_requires_approval_proposal():
    event = {"type": EventType.ACTION_PROPOSED.value, "payload": {"requires_approval": True, "title": "push to GitHub"}}
    msg = event_to_message(event)
    assert msg is not None and msg.kind == MessageKind.APPROVAL_REQUEST


def test_routine_event_not_reported():
    assert event_to_message({"type": EventType.OBSERVATION_RECORDED.value, "payload": {}}) is None
    assert event_to_message({"type": EventType.ACTION_PROPOSED.value, "payload": {"requires_approval": False}}) is None


# --- channel factory + telegram safety ---

def test_make_channel_defaults_to_local_inbox(tmp_path):
    ch = make_channel(ChannelConfig(root=str(tmp_path)))
    assert ch.name == "local_inbox"
    ch.send(OutboundMessage(title="x"))
    assert (tmp_path / "outbox.jsonl").exists()


def test_telegram_inactive_is_safe_noop():
    from yizhi.channels.telegram import TelegramChannel

    ch = TelegramChannel(ChannelConfig(kind="telegram"))  # no token -> inactive
    ch.send(OutboundMessage(title="should not send"))     # must not raise / hit network
    assert ch.poll() == []


def test_cli_report_offline(tmp_path, capsys):
    from yizhi.cli import main
    from yizhi.state.store import append_event

    db = tmp_path / "s.sqlite"
    append_event(EventType.JUDGMENT_RENDERED, "finding", "f1", {"verdict": "KILL", "subject": "BTC"}, path=db)
    rc = main(["--db", str(db), "report", "--channel-root", str(tmp_path / "ch")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "reported: 1" in out
    assert (tmp_path / "ch" / "outbox.jsonl").exists()
