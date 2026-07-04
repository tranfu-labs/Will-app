from __future__ import annotations

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.store import save_campaign_started
from yizhi.core.schemas import EventType
from yizhi.execution.delegation import FakeDelegationClient
from yizhi.liaison.chat import ChatIO, run_chat
from yizhi.state.store import init_db, list_events, load_latest_snapshot


def _io(lines: list[str]) -> ChatIO:
    feed = iter(lines)
    return ChatIO(input_fn=lambda prompt: next(feed), output_fn=lambda text: None)


def test_chat_answers_a_question_with_state_receipt(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    io = _io(["预算还剩多少？", "/quit"])

    rc = run_chat(db, io=io, llm=None, max_turns=5)

    assert rc == 0
    answer = "\n".join(io.transcript)
    assert "存续预算" in answer                       # deterministic receipt grounded in state
    assert "高显著性观察" in answer                    # the words entered the loop
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.OBSERVATION_RECORDED.value in event_types


def test_chat_vision_command_governs_state(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    io = _io(["vision 打赢 BTC 研究战争", "/quit"])

    run_chat(db, io=io, llm=None, max_turns=5)

    state = load_latest_snapshot(db)
    assert state.vision == "打赢 BTC 研究战争"
    assert EventType.VISION_SET.value in {e["type"] for e in list_events(path=db)}
    assert any("愿景已更新" in t for t in io.transcript)


def test_chat_research_runs_governed_delegation(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    client = FakeDelegationClient(ok=True, summary="要点", output_text="- BTC 减半周期约四年\n- 来源: bitcoin.org")
    io = _io(["/research BTC 减半", "/quit"])

    run_chat(db, io=io, llm=None, delegation_client=client, max_turns=5)

    assert client.called
    assert "减半" in client.last_task.instruction
    assert any("BTC 减半周期" in t for t in io.transcript)
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.DELEGATION_COMPLETED.value in event_types
    assert EventType.POLICY_GATE_PASSED.value in event_types
    assert EventType.BUDGET_SPENT.value in event_types  # research spends the will's currency


def test_chat_in_campaign_context_uses_campaign_environment(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-chat", workspace_root=tmp_path / "ws")
    save_campaign_started(db, campaign)
    io = _io(["战役进展如何？", "/quit"])

    run_chat(db, io=io, llm=None, campaign_id="btc-chat", max_turns=5)

    observations = [
        e for e in list_events(path=db)
        if e["type"] == EventType.OBSERVATION_RECORDED.value
        and e["payload"].get("environment") == "campaign"
    ]
    assert observations, "the utterance must be digested in the campaign environment"


def test_chat_status_and_empty_lines_do_not_step(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    io = _io(["/status", "/quit"])

    run_chat(db, io=io, llm=None, max_turns=5)

    assert any("存续预算" in t for t in io.transcript)
    loop_events = [e for e in list_events(path=db) if e["type"] == EventType.OBSERVATION_RECORDED.value]
    assert not loop_events                             # /status is free: no step, no observation
