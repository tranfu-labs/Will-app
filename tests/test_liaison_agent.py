from __future__ import annotations

import json

from yizhi.channels.base import InboundVerb
from yizhi.channels.local_inbox import LocalInboxChannel
from yizhi.core.schemas import Goal, WillState
from yizhi.liaison.agent import LiaisonAgent
from yizhi.liaison.store import LiaisonStore
from yizhi.liaison.tools import LiaisonTools
from yizhi.state.store import create_snapshot, init_db


def _agent(tmp_path, llm=None):
    db = init_db(tmp_path / "state.sqlite")
    create_snapshot(WillState(goals=[Goal(title="Find a funding edge")], loop_count=4), path=db)
    tools = LiaisonTools(db_path=db, channel_root=tmp_path / "channel", packet_path=tmp_path / "packet.json")
    store = LiaisonStore(tmp_path / "liaison.sqlite")
    return LiaisonAgent(tools, store, llm=llm), tmp_path / "channel", store


def test_status_query_replies_without_writing_inbox(tmp_path):
    agent, channel_root, _ = _agent(tmp_path)
    result = agent.handle_user_message("现在进展如何？")
    assert result.messages[-1].label == "status"
    assert "Find a funding edge" in result.messages[-1].text
    assert not (channel_root / "inbox.jsonl").exists()


def test_note_and_ask_go_to_will_inbox(tmp_path):
    agent, channel_root, _ = _agent(tmp_path)
    agent.handle_user_message("记一下手续费假设")
    agent.handle_user_message("为什么卡住了？")
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [
        (InboundVerb.NOTE, "记一下手续费假设"),
        (InboundVerb.ASK, "为什么卡住了？"),
    ]


def test_vision_and_kill_return_pending_confirmation(tmp_path):
    agent, channel_root, _ = _agent(tmp_path)
    vision = agent.handle_user_message("把愿景改成先证明一个真实可复现的 edge")
    kill = agent.handle_user_message("放弃当前目标")
    assert vision.pending_action and vision.pending_action.verb == "vision"
    assert kill.pending_action and kill.pending_action.verb == "kill"
    assert not (channel_root / "inbox.jsonl").exists()

    confirmed = agent.confirm_pending(kill.pending_action.id)
    assert confirmed.sent_command_id
    commands = LocalInboxChannel(channel_root).poll()
    assert [(c.verb, c.arg) for c in commands] == [(InboundVerb.KILL, "goal")]


def test_fake_llm_tool_loop_can_reply(tmp_path):
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system, user):
            self.calls += 1
            if self.calls == 1:
                return {"action": "tool", "tool": "get_state", "args": {}}
            payload = json.loads(user)
            assert payload["observations"]
            return {"action": "reply", "reply": "状态已读取。"}

    agent, channel_root, _ = _agent(tmp_path, llm=FakeLLM())
    result = agent.handle_user_message("看一下状态")
    assert result.messages[-1].text == "状态已读取。"
    assert not (channel_root / "inbox.jsonl").exists()


def test_bad_llm_decision_falls_back_to_deterministic(tmp_path):
    class BadLLM:
        def complete_json(self, system, user):
            return {"action": "tool", "tool": "delete_state", "args": {}}

    agent, channel_root, _ = _agent(tmp_path, llm=BadLLM())
    result = agent.handle_user_message("现在进展如何？")
    assert result.messages[-1].label == "status"
    assert not (channel_root / "inbox.jsonl").exists()
