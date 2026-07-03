"""novelty as world-model prediction error, carried forward to raise next-loop encoding."""

from __future__ import annotations

from yizhi.core.schemas import MemoryType, WillState
from yizhi.engine.findings import novelty_vs_prior
from yizhi.engine.loop import run_step
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.memory.backends import SqliteMemoryBackend
from yizhi.memory.salience import SalienceSignals, score_salience
from yizhi.state.snapshots import load_or_create_state


# ---- novelty_vs_prior (pure): world-model prediction error vs the prior belief ----

def test_novelty_vs_prior_is_full_without_a_prior():
    assert novelty_vs_prior(None, "anything") == 1.0          # first sighting is fully novel


def test_novelty_vs_prior_low_on_reconfirmation_high_on_divergence():
    prior = "[KILL] EDGEY funding-diff: net -50 bps, no edge at this threshold"
    reconfirm = "[KILL] EDGEY funding-diff: net -48 bps, no edge at this threshold"   # same belief
    diverge = "[PROMOTE] WIDGET sharpe persistent candidate winning structural spread"  # different
    assert novelty_vs_prior(prior, reconfirm) < novelty_vs_prior(prior, diverge)
    assert novelty_vs_prior(prior, diverge) > 0.5


# ---- novelty is a real salience signal, not decoration ----

def test_novelty_raises_salience_above_floor_zero():
    # On an EPISODIC memory (floor 0), novelty moves the score directly by its weight.
    base = score_salience(MemoryType.EPISODIC, SalienceSignals(novelty=0.0))
    surprised = score_salience(MemoryType.EPISODIC, SalienceSignals(novelty=1.0))
    assert surprised > base
    assert round(surprised - base, 4) == 0.15                 # the novelty weight


# ---- arousal carryover: last surprise raises next-loop observation salience ----

def _max_episodic_salience(db):
    return max((m.salience for m in SqliteMemoryBackend(db).all(live_only=True)
                if m.memory_type == MemoryType.EPISODIC.value), default=0.0)


def test_prior_surprise_raises_next_observation_salience(tmp_path):
    # A loop that starts with last_surprise=1.0 (the previous finding fully departed from belief)
    # encodes its observations more strongly than a calm loop — same env, everything else equal.
    calm_db = tmp_path / "calm.sqlite"
    run_step(SelfRepoEnvironment(), load_or_create_state(calm_db), calm_db)   # last_surprise 0

    surprised_db = tmp_path / "surprised.sqlite"
    surprised = load_or_create_state(surprised_db)
    surprised.last_surprise = 1.0
    run_step(SelfRepoEnvironment(), surprised, surprised_db)

    assert _max_episodic_salience(surprised_db) > _max_episodic_salience(calm_db)
