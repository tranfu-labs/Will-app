from will.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    DelegationKind,
    DelegationReport,
    DelegationTask,
    EnvironmentName,
    EventType,
    ExistenceBudget,
    IdentityProfile,
    PolicyGateResult,
    ValuePolicy,
    VerificationResult,
    WillState,
)


def assert_round_trip(model):
    encoded = model.model_dump_json()
    decoded = type(model).model_validate_json(encoded)
    assert decoded == model


def test_default_identity_contract():
    state = WillState()
    assert state.identity.name == "Will"
    assert state.identity.role == "Autonomous Campaign Harness"
    assert "no live trading" in state.identity.non_goals
    assert "no credentials" in state.identity.non_goals
    assert "no reproduction" in state.identity.non_goals
    assert "no external mutation of campaign state, policy, budget, or ledger" in state.identity.non_goals
    assert state.active_campaign_ids == []


def test_public_schemas_json_round_trip():
    state = WillState()
    proposal = ActionProposal(
        environment=EnvironmentName.SELF_REPO,
        action_class=ActionClass.INTERNAL,
        title="git status",
        command=["git", "status", "--short", "--branch"],
    )
    policy = PolicyGateResult(proposal_id=proposal.id, allowed=True, decision="allow")
    action = ActionRecord(
        proposal_id=proposal.id,
        environment=EnvironmentName.SELF_REPO,
        status=ActionStatus.SUCCEEDED,
        command=proposal.command,
        exit_code=0,
    )
    verification = VerificationResult(action_record_id=action.id, passed=True, summary="ok")
    delegation = DelegationTask(
        kind=DelegationKind.ANALYZE_REPO,
        instruction="inspect",
        cwd=".",
        allowed_tools=["rg", "sed"],
    )
    report = DelegationReport(task_id=delegation.id, ok=True, summary="ok")
    for model in [
        state,
        IdentityProfile(),
        ValuePolicy(),
        ExistenceBudget(),
        proposal,
        policy,
        action,
        verification,
        delegation,
        report,
    ]:
        assert_round_trip(model)


def test_event_type_surface_excludes_removed_cognition_loop():
    values = {e.value for e in EventType}
    assert "ThoughtEventGenerated" not in values
    assert "MemoryCreated" not in values
    assert "PlanCreated" not in values
    assert "CampaignStarted" in values
    assert "StageDecisionRecorded" in values
