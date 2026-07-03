"""Default v0 policy gate."""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    EnvironmentName,
    PolicyGateResult,
    ValuePolicy,
    WillState,
)

ARBBOT_FORBIDDEN_PATTERNS = [
    "--live",
    "--live-public",
    "place_order",
    "cancel_order",
    "set_leverage",
    "apiKey",
    "secret",
    "ExecutionVenue(",
    "private",
    "credential",
]

ARBBOT_ALLOWED_COMMANDS = {
    ("git", "status", "--short", "--branch"),
    ("make", "test"),
    ("make", "safety"),
    ("make", "smoke"),
    ("python", "scripts/smoke_funding_diff_scan.py", "--dry-run"),
    ("python", "scripts/smoke_fundarb_public_scan.py", "--dry-run"),
}

# The in-process backtest probe (BACKTEST_SENTINEL) is a PURE function call (no
# subprocess, no network, no orders), so it is gated by STRUCTURE, not an exact tuple —
# enabling parameterized authoring (symbol/params chosen at runtime) while staying safe:
# whatever the params, the sentinel can only run a read-only funding-diff backtest.
BACKTEST_SENTINEL = "yizhi:arbbot-backtest"
_BACKTEST_PARAM_KEYS = {"symbol", "min_net_bps", "horizon_hours"}


def _valid_backtest_command(command: list[str]) -> bool:
    if len(command) < 2 or command[1] != "funding_diff":
        return False
    for arg in command[2:]:
        if "=" not in arg:
            return False
        key, _, value = arg.partition("=")
        if key not in _BACKTEST_PARAM_KEYS:
            return False
        if key == "symbol":
            if not value or not value.replace("_", "").isalnum():
                return False
        else:
            try:
                float(value)
            except ValueError:
                return False
    return True

SELF_REPO_ALLOWED_COMMANDS = {
    ("git", "status", "--short", "--branch"),
    ("python3", "-m", "json.tool", "data/papers/manifest.json"),
    ("python3", "-m", "json.tool", "data/sources/manifest.json"),
}


def command_text(command: list[str]) -> str:
    return " ".join(command)


# pi_agent delegation (R0; docs/resident-operator-plan.md). A delegation rides as a
# NETWORK_READ ActionProposal whose command is the sentinel + kind, with the full
# DelegationTask in metadata. v0 is READ-ONLY: only read kinds, no write tools, no
# write flag, and an in-repo relative cwd. Write/apply is a later governed stage.
DELEGATION_SENTINEL = "yizhi:delegate"
_DELEGATION_READONLY_KINDS = {"analyze_repo", "summarize_tests", "inspect_docs"}
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

    if proposal.environment == EnvironmentName.ARBBOT:
        text = command_text(proposal.command)
        for pattern in ARBBOT_FORBIDDEN_PATTERNS:
            if pattern in text:
                reasons.append(f"ArbBot command contains forbidden pattern: {pattern}")
        if proposal.command and proposal.command[0] == BACKTEST_SENTINEL:
            if not _valid_backtest_command(proposal.command):
                reasons.append("ArbBot backtest command failed structural validation")
        elif tuple(proposal.command) not in ARBBOT_ALLOWED_COMMANDS:
            reasons.append("ArbBot command is not in v0 allowlist")

    if proposal.environment == EnvironmentName.SELF_REPO and proposal.command:
        if tuple(proposal.command) not in SELF_REPO_ALLOWED_COMMANDS:
            reasons.append("self_repo command is not in v0 allowlist")

    if proposal.environment == EnvironmentName.PI_AGENT:
        reasons.extend(_delegation_reasons(proposal))

    allowed = len(reasons) == 0
    return PolicyGateResult(
        proposal_id=proposal.id,
        allowed=allowed,
        decision="allow" if allowed else "deny",
        reasons=reasons,
    )
