from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    AutonomousValueLoop,
    DriveSignal,
    EnvironmentName,
    EvalEvent,
    Goal,
    IdentityProfile,
    Intention,
    LoopStatus,
    MemoryRecord,
    Plan,
    PlanStep,
    PolicyGateResult,
    Reflection,
    SkillRecord,
    ThoughtEvent,
    ValuePolicy,
    VerificationResult,
    WillState,
    WorldObservation,
)


def assert_round_trip(model):
    encoded = model.model_dump_json()
    decoded = type(model).model_validate_json(encoded)
    assert decoded.id == model.id


def test_default_identity_contract():
    state = WillState()
    assert state.identity.name == "Will"
    assert state.identity.role == "local governed will agent"
    assert "no live trading" in state.identity.non_goals
    assert "no credentials" in state.identity.non_goals
    assert "no reproduction" in state.identity.non_goals
    assert "no silent core memory mutation" in state.identity.non_goals


def test_public_schemas_json_round_trip():
    state = WillState()
    obs = WorldObservation(environment=EnvironmentName.SELF_REPO, source="test", summary="ok")
    thought = ThoughtEvent(kind="maintenance", content="ok")
    drive = DriveSignal(name="maintenance_pressure", intensity=0.2, reason="ok")
    memory = MemoryRecord(kind="reflection", content="ok")
    intention = Intention(title="test", rationale="ok", active=True)
    plan = Plan(goal_id="goal-1", steps=[PlanStep(description="one", target_command=["git", "status"])])
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
    reflection = Reflection(loop_id="loop-test", content="ok", next_memory=memory)
    skill = SkillRecord(name="test", description="ok")
    eval_event = EvalEvent(loop_id="loop-test", status=LoopStatus.FULL)
    loop = AutonomousValueLoop(status=LoopStatus.FULL, environment=EnvironmentName.SELF_REPO)
    for model in [
        state,
        IdentityProfile(),
        ValuePolicy(),
        Goal(title="g"),
        obs,
        thought,
        drive,
        memory,
        intention,
        plan,
        proposal,
        policy,
        action,
        verification,
        reflection,
        skill,
        eval_event,
        loop,
    ]:
        assert_round_trip(model)
