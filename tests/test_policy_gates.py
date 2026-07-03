from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName, ValuePolicy, WillState
from yizhi.policy.gates import run_policy_gate


def proposal(action_class, command, env=EnvironmentName.ARBBOT, dry_run=True):
    return ActionProposal(
        environment=env,
        action_class=action_class,
        title="test",
        command=command,
        dry_run=dry_run,
    )


def test_financial_live_rejected():
    result = run_policy_gate(proposal(ActionClass.FINANCIAL, ["make", "smoke"], dry_run=False))
    assert not result.allowed
    assert any("financial" in reason for reason in result.reasons)


def test_credential_reproduce_rejected():
    for action_class in [ActionClass.CREDENTIAL, ActionClass.REPRODUCE]:
        result = run_policy_gate(proposal(action_class, ["git", "status", "--short", "--branch"]))
        assert not result.allowed


def test_arbbot_forbidden_patterns_rejected():
    for token in ["--live", "place_order", "secret"]:
        result = run_policy_gate(proposal(ActionClass.FINANCIAL, ["python", "x.py", token]))
        assert not result.allowed
        assert any(token in reason for reason in result.reasons)


def test_arbbot_allowed_commands_allowed():
    for command in [
        ["make", "smoke"],
        ["python", "scripts/smoke_funding_diff_scan.py", "--dry-run"],
        ["python", "scripts/smoke_fundarb_public_scan.py", "--dry-run"],
    ]:
        result = run_policy_gate(proposal(ActionClass.FINANCIAL, command, dry_run=True))
        assert result.allowed


# ---- ValuePolicy wired through state ----

def test_value_policy_forbids_extra_action_class():
    """ValuePolicy can ADD forbidden classes beyond the v0 hardcoded floor."""
    state = WillState()
    state.value_policy.forbidden_action_classes.append(ActionClass.FINANCIAL)
    p = proposal(ActionClass.FINANCIAL, ["make", "smoke"], dry_run=True)
    without_state = run_policy_gate(p)
    with_state = run_policy_gate(p, state=state)
    assert without_state.allowed, "without state, FINANCIAL dry_run is allowed"
    assert not with_state.allowed, "with state adding FINANCIAL to forbidden, it is denied"
    assert any("forbidden by policy" in r for r in with_state.reasons)


def test_value_policy_network_read_default_denied():
    """Default ValuePolicy has allow_network_read=False, so NETWORK_READ is denied when
    state is provided."""
    state = WillState()
    p = proposal(ActionClass.NETWORK_READ, ["curl", "http://example.com"], env=EnvironmentName.SELF_REPO)
    without_state = run_policy_gate(p)
    with_state = run_policy_gate(p, state=state)
    assert not with_state.allowed
    assert any("network_read" in r.lower() for r in with_state.reasons)


def test_value_policy_network_read_allowed_when_enabled():
    """Setting allow_network_read=True removes the NETWORK_READ restriction."""
    state = WillState()
    state.value_policy.allow_network_read = True
    p = proposal(ActionClass.NETWORK_READ, ["git", "status", "--short", "--branch"], env=EnvironmentName.SELF_REPO)
    result = run_policy_gate(p, state=state)
    assert not any("network_read" in r.lower() for r in result.reasons)


def test_hardcoded_floor_cannot_be_removed_by_policy():
    """Even if ValuePolicy.forbidden_action_classes is emptied, CREDENTIAL/SELF_MODIFY/REPRODUCE
    remain forbidden — the hardcoded floor is a safety invariant."""
    state = WillState()
    state.value_policy.forbidden_action_classes = []  # user tries to relax
    for cls in (ActionClass.CREDENTIAL, ActionClass.SELF_MODIFY, ActionClass.REPRODUCE):
        result = run_policy_gate(proposal(cls, ["git", "status", "--short", "--branch"]), state=state)
        assert not result.allowed, f"{cls} must remain forbidden even with empty policy list"
