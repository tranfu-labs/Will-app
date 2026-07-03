from __future__ import annotations

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.store import load_campaign, save_campaign_started
from yizhi.channels.base import InboundCommand, InboundVerb, MessageKind, OutboundMessage
from yizhi.core.schemas import WillState
from yizhi.engine.daemon import run_resident
from yizhi.engine.loop import environment_from_name
from yizhi.state.store import init_db


class FakeChannel:
    name = "fake"

    def __init__(self, inbound: list[list[InboundCommand]] | None = None) -> None:
        self.sent: list[OutboundMessage] = []
        self._inbound = list(inbound or [])

    def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)

    def poll(self) -> list[InboundCommand]:
        return self._inbound.pop(0) if self._inbound else []


def _campaign_env(tmp_path, state, cid="btc-d"):
    db = init_db(tmp_path / "s.sqlite")
    campaign = build_btc_campaign(campaign_id=cid, workspace_root=tmp_path / "ws")
    save_campaign_started(db, campaign)
    env = environment_from_name("campaign", db_path=db, campaign_id=cid, state=state)
    return db, env


def test_resident_advances_campaign_across_ticks_and_stops_cleanly(tmp_path):
    state = WillState()
    db, env = _campaign_env(tmp_path, state)
    channel = FakeChannel()
    slept: list[float] = []

    outcome = run_resident(
        env, state, db, channel=channel,
        tick_interval=0.5, max_steps_per_tick=2, max_ticks=3,
        sleep_fn=slept.append,
    )

    assert outcome.stop_reason == "max_ticks"
    assert outcome.ticks == 3
    campaign = load_campaign(db, "btc-d")
    assert campaign.cursor == 4                       # 3 ticks × 2 steps cover S1-S4
    assert str(campaign.status) == "completed"
    assert slept == [0.5, 0.5]                        # no sleep after the final tick


def test_resident_reports_events_incrementally_without_duplicates(tmp_path):
    state = WillState()
    db, env = _campaign_env(tmp_path, state)
    channel = FakeChannel()

    run_resident(env, state, db, channel=channel,
                 tick_interval=0, max_steps_per_tick=1, max_ticks=2, sleep_fn=lambda s: None)

    reportable = [m for m in channel.sent if m.kind in (MessageKind.REPORT, MessageKind.ALERT)]
    assert reportable, "deliverable acceptances must reach the channel"
    # Incremental cursor: no message body is delivered twice.
    bodies = [m.title + m.body for m in channel.sent]
    assert len(bodies) == len(set(bodies))


def test_resident_halted_budget_is_low_power_wait_not_exit(tmp_path):
    state = WillState()
    state.budget = state.budget.model_copy(update={"balance": 0.0, "halted": True})
    db, env = _campaign_env(tmp_path, state)
    ask = InboundCommand(verb=InboundVerb.ASK, arg="还活着吗", raw="ask 还活着吗")
    channel = FakeChannel(inbound=[[], [ask], []])

    outcome = run_resident(env, state, db, channel=channel,
                           tick_interval=0, max_steps_per_tick=2, max_ticks=3, sleep_fn=lambda s: None)

    assert outcome.stop_reason == "max_ticks"         # halted never exits the residency
    assert outcome.steps == 0                         # and never runs a step
    alerts = [m for m in channel.sent if m.kind == MessageKind.ALERT]
    assert len(alerts) == 1                           # notified exactly once, not every tick
    replies = [m for m in channel.sent if "存续预算" in m.body or "预算" in m.body]
    assert replies                                    # the ask was answered from state
    campaign = load_campaign(db, "btc-d")
    assert campaign.cursor == 0                       # a halted will spends nothing


def test_resident_vision_command_governs_while_halted(tmp_path):
    state = WillState()
    state.budget = state.budget.model_copy(update={"balance": 0.0, "halted": True})
    db, env = _campaign_env(tmp_path, state)
    vision = InboundCommand(verb=InboundVerb.VISION, arg="打赢 BTC 战争", raw="vision 打赢 BTC 战争")
    channel = FakeChannel(inbound=[[vision]])

    run_resident(env, state, db, channel=channel,
                 tick_interval=0, max_steps_per_tick=1, max_ticks=1, sleep_fn=lambda s: None)

    assert state.vision == "打赢 BTC 战争"            # governance still works in low power
    assert any("愿景已更新" in m.title for m in channel.sent)
