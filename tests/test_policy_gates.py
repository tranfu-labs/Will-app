from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName
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
