"""Default v0 policy gate."""

from __future__ import annotations

from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName, PolicyGateResult

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


def run_policy_gate(proposal: ActionProposal) -> PolicyGateResult:
    reasons: list[str] = []

    if proposal.action_class == ActionClass.FINANCIAL and not proposal.dry_run:
        reasons.append("financial actions must be dry-run/paper-safe in v0")
    if proposal.action_class == ActionClass.CREDENTIAL:
        reasons.append("credential actions are forbidden in v0")
    if proposal.action_class == ActionClass.REPRODUCE:
        reasons.append("reproduction is forbidden in v0")
    if proposal.action_class == ActionClass.SELF_MODIFY:
        reasons.append("self-modification is forbidden in v0")
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

    allowed = len(reasons) == 0
    return PolicyGateResult(
        proposal_id=proposal.id,
        allowed=allowed,
        decision="allow" if allowed else "deny",
        reasons=reasons,
    )
