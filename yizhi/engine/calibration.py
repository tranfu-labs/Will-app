"""Calibration — the agent scoring its own predictions (metamemory).

Before running an experiment probe, the agent predicts (confidence in [0,1]) that
it will produce NEW verified edge-knowledge. After the loop, the outcome is known
deterministically (did the knowledge bonus fire?), so the prediction is scored by
a Brier score — objectively, NOT by the LLM grading itself. Accumulated, this is
the agent's real track record: "when I expect an edge, am I right?" It is written
as subject-keyed CALIBRATION memory and surfaces in standing recall, so the agent
sees its own reliability (docs/theory-of-memory.md sec 8.2). Deterministic default:
no LLM -> no prediction -> no calibration.
"""

from __future__ import annotations

from yizhi.engine.recall_render import render_recall

_PREDICT_SYSTEM = (
    "You are yizhi predicting whether the experiment you are about to run will "
    "produce NEW, verified edge-knowledge about ArbBot — something you do not "
    "already know. Be honest and calibrated: high confidence only when you expect "
    "genuinely new evidence, low when you expect to merely re-confirm the known. "
    'Respond with a single JSON object: {"confidence": <number in [0,1]>, '
    '"rationale": "<one sentence>"}.'
)


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def predict_value(llm, proposal, recalled, on_fallback=None) -> float | None:
    """The agent's confidence that this experiment will yield new verified
    knowledge, or None (no prediction) when the engine is off, the action is not an
    experiment probe, or the prediction fails."""
    if llm is None or not getattr(proposal, "experiment", False):
        return None
    lines = [f"action: {proposal.title} :: {' '.join(proposal.command)} — {proposal.description}"]
    block = render_recall(recalled or [], k=6, label="already known")
    if block:
        lines.append(block)
    try:
        result = llm.complete_json(_PREDICT_SYSTEM, "\n".join(lines))
        return _clamp(float(result.get("confidence", 0.5)))
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None


def brier(confidence: float, outcome: float) -> float:
    """Brier score for a single prediction: 0 = perfect, 1 = worst."""
    return (confidence - outcome) ** 2


def summarize_calibration(scored: list[dict]) -> str:
    """A one-line running track record from the scored predictions."""
    n = len(scored)
    if n == 0:
        return "calibration: no scored predictions yet"
    mean_brier = sum(s.get("brier", 0.0) for s in scored) / n
    hits = sum(1 for s in scored if (s.get("confidence", 0.0) >= 0.5) == (s.get("outcome", 0.0) >= 0.5))
    return (
        f"calibration over {n} predictions: mean Brier {mean_brier:.2f} (0=perfect, 1=worst), "
        f"directional hit-rate {hits}/{n}"
    )
