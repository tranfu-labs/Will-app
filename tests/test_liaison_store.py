from __future__ import annotations

from yizhi.liaison.schemas import LiaisonMessage, LiaisonPendingAction
from yizhi.liaison.store import LiaisonStore, default_liaison_db_path


def test_default_liaison_db_sits_next_to_will_db(tmp_path):
    assert default_liaison_db_path(tmp_path / "state.sqlite") == tmp_path / "liaison.sqlite"


def test_liaison_store_round_trips_messages_and_pending_action(tmp_path):
    store = LiaisonStore(tmp_path / "liaison.sqlite")
    pending = LiaisonPendingAction(
        verb="vision",
        text="prove one real edge",
        risk="high",
        confirmation_prompt="确认修改愿景？",
    )
    store.append(LiaisonMessage(source="human", label="human", text="hello"))
    stored = store.append(
        LiaisonMessage(source="liaison", label="confirm", text="确认修改愿景？", pending_action=pending)
    )

    messages = store.list_messages()
    assert [m.source for m in messages] == ["human", "liaison"]
    assert messages[-1].pending_action and messages[-1].pending_action.verb == "vision"
    found = store.get_pending(stored.pending_action.id)
    assert found is not None and found.text == "prove one real edge"
