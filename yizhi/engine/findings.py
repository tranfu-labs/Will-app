"""Edge-knowledge extraction: turn an action's real output into durable, queryable
project knowledge (the experiment ledger).

Reflection (engine/reflection.py) records what *yizhi* learned about its process.
This module records what yizhi learned about *ArbBot / the world* from an action's
actual output — a structured finding keyed by a stable subject. Written as
subject-keyed semantic memory (the converged architecture's "project record",
docs/theory-of-memory.md sec 8.1: project state is semantic-with-a-subject, not a
new type), so re-running the same probe supersedes the prior finding and the
ledger stays current. Grounded to the command that produced it. Deterministic
default: no LLM -> no finding (the ledger only fills when the engine is on).
"""

from __future__ import annotations

import re

from yizhi.core.schemas import ActionRecord, VerificationResult
from yizhi.memory.text import overlap

# Below this text overlap with the probe's prior finding, a finding counts as new
# knowledge. A rephrasing of the same finding overlaps highly (not new); a finding
# that reveals something different overlaps little (new).
NOVELTY_THRESHOLD = 0.5

_FINDING_SYSTEM = (
    "You are yizhi extracting durable knowledge about ArbBot from an action's "
    "output. Produce one finding about ArbBot or the market that this output "
    "revealed — NOT about yizhi's own process or safety. If the output reveals "
    'nothing durable, return an empty string. Respond with a single JSON object: '
    '{"finding": "<one concrete sentence of knowledge grounded in the output>"}.'
)


def probe_subject(command: list[str]) -> str:
    """A deterministic ledger key for the probe that produced a finding. Keying by
    the command (not an LLM-chosen string) makes re-running the same probe reliably
    supersede its prior finding, so the experiment ledger stays current per probe
    rather than piling up near-duplicates under drifting keys."""
    slug = re.sub(r"[^a-z0-9]+", "-", " ".join(command).lower()).strip("-")
    return f"arbbot/probe/{slug}" if slug else "arbbot/probe/unknown"


def extract_finding(
    llm,
    action: ActionRecord | None,
    verification: VerificationResult | None,
    on_fallback=None,
) -> str | None:
    """Return a one-sentence finding extracted from the action's output, or None.
    None whenever the engine is off, there is no output, or extraction fails — so
    the ledger only accumulates real, grounded knowledge. The caller keys it by
    `probe_subject(command)`."""
    if llm is None or action is None:
        return None
    output = "\n".join(part for part in [(action.stdout or "").strip(), (action.stderr or "").strip()] if part)
    if not output:
        return None
    user = (
        f"action: {' '.join(action.command)}\n"
        f"verified: {bool(verification and verification.passed)}\n"
        f"output (truncated):\n{output[:1200]}"
    )
    try:
        result = llm.complete_json(_FINDING_SYSTEM, user)
        finding = str(result.get("finding", "")).strip()
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None
    return finding or None


def is_new_knowledge(prior_content: str | None, content: str) -> bool:
    """True if `content` is genuinely new vs the probe's prior finding — used to
    decide whether to replenish the budget. No prior finding is always new; a
    rephrasing of the same finding (high overlap) is not, so re-confirming what is
    already known earns nothing and net-drains the budget."""
    if not prior_content:
        return True
    return overlap(content, [prior_content]) < NOVELTY_THRESHOLD


def novelty_vs_prior(prior_content: str | None, content: str) -> float:
    """World-model prediction error as a salience signal, in [0, 1]: how far this finding departs
    from the prior belief about the SAME subject (the ledger entry — yizhi's standing model of that
    subject). No prior is fully novel (1.0); a re-confirmation that overlaps the prior is low; a
    finding that diverges (e.g. a flipped verdict) is high. The continuous companion to
    is_new_knowledge's threshold gate, on the same overlap metric."""
    if not prior_content:
        return 1.0
    return max(0.0, 1.0 - overlap(content, [prior_content]))
