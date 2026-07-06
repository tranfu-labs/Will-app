"""Default v0 policy gate."""

from __future__ import annotations

from pathlib import Path

from will.core.schemas import (
    ActionClass,
    ActionProposal,
    EnvironmentName,
    PolicyGateResult,
    WillState,
)

SELF_REPO_ALLOWED_COMMANDS = {
    ("git", "status", "--short", "--branch"),
    ("python3", "-m", "json.tool", "data/papers/manifest.json"),
    ("python3", "-m", "json.tool", "data/sources/manifest.json"),
}


def command_text(command: list[str]) -> str:
    return " ".join(command)


# pi_agent delegation: read-only reports and patch drafting behind policy gates.
# A delegation rides as a NETWORK_READ ActionProposal whose command is the sentinel
# + kind, with the full DelegationTask in metadata. The worker NEVER writes: R0
# kinds return analysis text, and R1's propose_patch returns a unified diff as
# TEXT — the deterministic patch validator and the artifact write live on this
# side of the boundary. Apply remains a separate, later governed stage (R4).
DELEGATION_SENTINEL = "will:delegate"
_DELEGATION_READONLY_KINDS = {"analyze_repo", "research_topic", "run_analysis", "propose_patch"}
_DELEGATION_FORBIDDEN_TOOL_PATTERNS = ["write", "edit", "create", "delete", "commit", "push", "bash", "shell"]


def _safe_delegation_cwd(cwd: str) -> bool:
    if not cwd or cwd.startswith("/") or cwd.startswith("~"):
        return False
    return ".." not in Path(cwd).parts


def _delegation_reasons(proposal: ActionProposal) -> list[str]:
    reasons: list[str] = []
    if not proposal.command or proposal.command[0] != DELEGATION_SENTINEL:
        reasons.append("pi_agent action must use the delegation sentinel")
    task = proposal.metadata.get("delegation_task")
    if not isinstance(task, dict):
        reasons.append("pi_agent delegation requires a structured delegation_task in metadata")
        return reasons
    kind = task.get("kind")
    if task.get("allow_write", False):
        reasons.append("pi_agent delegation must be read-only in v0 (allow_write is forbidden)")
    if kind not in _DELEGATION_READONLY_KINDS:
        reasons.append(f"pi_agent delegation kind '{kind}' is not in the v0 read-only allowlist")
    if proposal.command and proposal.command[0] == DELEGATION_SENTINEL:
        if len(proposal.command) < 2 or proposal.command[1] != f"kind={kind}":
            reasons.append("pi_agent delegation command does not match the task kind")
    if not _safe_delegation_cwd(str(task.get("cwd", ""))):
        reasons.append("pi_agent delegation cwd must be a restricted in-repo relative path")
    for tool in task.get("allowed_tools", []):
        low = str(tool).lower()
        if any(p in low for p in _DELEGATION_FORBIDDEN_TOOL_PATTERNS):
            reasons.append(f"pi_agent delegation tool '{tool}' implies a non-read-only capability")
    return reasons


# Campaign actions (ADR-004 B1). The will drives the campaign harness through
# exactly three structural sentinels: tick (advance), revisit (rework — must
# carry evidence, not a whim), report (surface state). All are in-process
# state-machine operations; a tick's delegated worker is separately governed
# inside execute_delegation.
CAMPAIGN_SENTINEL = "will:campaign"
_CAMPAIGN_OPS = {"tick", "revisit", "report"}


def _campaign_reasons(proposal: ActionProposal) -> list[str]:
    reasons: list[str] = []
    if not proposal.command or proposal.command[0] != CAMPAIGN_SENTINEL:
        reasons.append("campaign action must use the campaign sentinel")
        return reasons
    op = proposal.metadata.get("campaign_op")
    if not isinstance(op, dict):
        reasons.append("campaign action requires structured campaign_op metadata")
        return reasons
    kind = op.get("op")
    if kind not in _CAMPAIGN_OPS:
        reasons.append(f"campaign op '{kind}' is not in the allowlist")
    if len(proposal.command) < 2 or proposal.command[1] != kind:
        reasons.append("campaign command does not match the op")
    if not op.get("campaign_id"):
        reasons.append("campaign op requires a campaign_id")
    if kind == "revisit":
        if not op.get("stage_id") or not str(op.get("note", "")).strip():
            reasons.append("campaign revisit requires stage_id and a non-empty note")
        if not op.get("evidence"):
            reasons.append("campaign revisit requires evidence (deliverable/judgment id)")
    return reasons


_V0_HARDCODED_FORBIDDEN = frozenset({
    ActionClass.CREDENTIAL,
    ActionClass.SELF_MODIFY,
    ActionClass.REPRODUCE,
})


def run_policy_gate(
    proposal: ActionProposal,
    *,
    state: WillState | None = None,
) -> PolicyGateResult:
    reasons: list[str] = []

    # v0 hardcoded floor: these classes are always forbidden regardless of ValuePolicy.
    # ValuePolicy can only ADD to this set, never shrink it.
    forbidden: frozenset[ActionClass] = _V0_HARDCODED_FORBIDDEN
    if state is not None:
        policy = state.value_policy
        forbidden = forbidden | frozenset(policy.forbidden_action_classes)
        if not policy.allow_network_read:
            forbidden = forbidden | {ActionClass.NETWORK_READ}

    if proposal.action_class in forbidden:
        reasons.append(f"{proposal.action_class} is forbidden by policy")

    if proposal.action_class == ActionClass.FINANCIAL and not proposal.dry_run:
        reasons.append("financial actions must be dry-run/paper-safe in v0")
    if proposal.action_class == ActionClass.EXTERNAL_WRITE:
        if proposal.requires_approval:
            reasons.append("external_write requires approval; v0 may propose but not execute")
        else:
            reasons.append("external_write without explicit approval requirement is forbidden")

    if proposal.environment == EnvironmentName.SELF_REPO and proposal.command:
        if tuple(proposal.command) not in SELF_REPO_ALLOWED_COMMANDS:
            reasons.append("self_repo command is not in v0 allowlist")

    if proposal.environment == EnvironmentName.PI_AGENT:
        reasons.extend(_delegation_reasons(proposal))

    if proposal.environment == EnvironmentName.CAMPAIGN:
        reasons.extend(_campaign_reasons(proposal))

    allowed = len(reasons) == 0
    return PolicyGateResult(
        proposal_id=proposal.id,
        allowed=allowed,
        decision="allow" if allowed else "deny",
        reasons=reasons,
    )
