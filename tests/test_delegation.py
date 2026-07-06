"""Governed read-only delegation to an external coding harness.

Offline and deterministic: a FakeDelegationClient stands in for the real CLI, so the
suite never starts a subprocess or touches the network. These tests pin the safety
contract (read-only only) and the governance closure (gate → budget → run → verify →
events).
"""

from __future__ import annotations

from will.core.schemas import (
    ActionClass,
    ActionStatus,
    DelegationKind,
    DelegationTask,
    EventType,
    ExistenceBudget,
)
from will.autonomy.budget import action_cost
from will.workers.delegation import (
    FakeDelegationClient,
    build_delegation_proposal,
    execute_delegation,
)
from will.autonomy.gates import run_policy_gate
from will.ledger.store import list_events


def _task(**over) -> DelegationTask:
    base = dict(
        kind=DelegationKind.ANALYZE_REPO,
        instruction="Summarize BTC campaign harness modules.",
        cwd="will/campaigns",
        allowed_tools=["Read", "Grep", "Glob"],
    )
    base.update(over)
    return DelegationTask(**base)


# --- safety contract: the gate keeps delegation read-only ---

def test_readonly_delegation_passes_policy():
    gate = run_policy_gate(build_delegation_proposal(_task()))
    assert gate.allowed, gate.reasons


def test_write_flag_denied():
    gate = run_policy_gate(build_delegation_proposal(_task(allow_write=True)))
    assert not gate.allowed
    assert any("read-only" in r for r in gate.reasons)


def test_kind_allowlist_boundary():
    # R1: propose_patch is now allowed — the worker still only returns diff TEXT
    # (write tools stay denied; the validator/archive live outside the worker).
    assert run_policy_gate(build_delegation_proposal(_task(kind=DelegationKind.PROPOSE_PATCH))).allowed
    # A kind outside the allowlist is still denied structurally.
    forged = build_delegation_proposal(_task())
    forged.metadata["delegation_task"]["kind"] = "exfiltrate_repo"
    forged.command = [forged.command[0], "kind=exfiltrate_repo"]
    gate = run_policy_gate(forged)
    assert not gate.allowed
    assert any("read-only allowlist" in r for r in gate.reasons)


def test_write_tool_denied():
    gate = run_policy_gate(build_delegation_proposal(_task(allowed_tools=["Read", "Write"])))
    assert not gate.allowed
    assert any("non-read-only capability" in r for r in gate.reasons)


def test_cwd_escape_denied():
    assert not run_policy_gate(build_delegation_proposal(_task(cwd="/etc"))).allowed
    assert not run_policy_gate(build_delegation_proposal(_task(cwd="../secrets"))).allowed


# --- governance closure: gate → budget → run → verify → events ---

def test_delegation_charges_budget_and_runs(tmp_path):
    db = tmp_path / "s.sqlite"
    client = FakeDelegationClient()
    budget = ExistenceBudget()
    outcome = execute_delegation(build_delegation_proposal(_task()), client, budget, db)
    assert client.called
    assert outcome.verification is not None and outcome.verification.passed
    assert outcome.budget.balance == budget.balance - action_cost(ActionClass.NETWORK_READ)


def test_delegation_emits_events(tmp_path):
    db = tmp_path / "s.sqlite"
    execute_delegation(build_delegation_proposal(_task()), FakeDelegationClient(), ExistenceBudget(), db)
    types = {e["type"] for e in list_events(path=db)}
    assert EventType.DELEGATION_REQUESTED.value in types
    assert EventType.DELEGATION_COMPLETED.value in types
    assert EventType.BUDGET_SPENT.value in types


def test_denied_delegation_never_runs_harness(tmp_path):
    db = tmp_path / "s.sqlite"
    client = FakeDelegationClient()
    outcome = execute_delegation(build_delegation_proposal(_task(allow_write=True)), client, ExistenceBudget(), db)
    assert not client.called
    assert outcome.record is not None and outcome.record.status == ActionStatus.BLOCKED
    types = {e["type"] for e in list_events(path=db)}
    assert EventType.POLICY_GATE_DENIED.value in types
    assert EventType.DELEGATION_COMPLETED.value not in types


def test_failed_harness_records_failure(tmp_path):
    db = tmp_path / "s.sqlite"
    outcome = execute_delegation(build_delegation_proposal(_task()), FakeDelegationClient(ok=False), ExistenceBudget(), db)
    assert outcome.verification is not None and not outcome.verification.passed
    types = {e["type"] for e in list_events(path=db)}
    assert EventType.DELEGATION_FAILED.value in types


def test_cli_delegate_runs_offline(tmp_path, capsys):
    from will.cli import main

    db = tmp_path / "s.sqlite"
    rc = main(["--db", str(db), "delegate", "--instruction", "map campaign modules", "--cwd", "will/campaigns"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "policy decision: allow" in out   # read-only default passes the gate
    assert "disabled" in out                  # harness off by default -> no subprocess started
