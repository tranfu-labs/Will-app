from __future__ import annotations

from will.core.schemas import DelegationKind, DelegationTask, EventType, ExistenceBudget
from will.workers.delegation import FakeDelegationClient, build_delegation_proposal
from will.workers.patches import (
    parse_patch_files,
    propose_patch_via_delegation,
    validate_patch_text,
)
from will.autonomy.gates import run_policy_gate
from will.ledger.store import init_db, list_events

GOOD_DIFF = """\
diff --git a/will/core/example.py b/will/core/example.py
--- a/will/core/example.py
+++ b/will/core/example.py
@@ -1,3 +1,4 @@
 def f():
+    # bounded by the caller
     return 1
"""


def _task(kind=DelegationKind.PROPOSE_PATCH, tools=("Read", "Grep", "Glob")):
    return DelegationTask(kind=kind, instruction="draft", cwd="will", allowed_tools=list(tools))


def test_gate_allows_propose_patch_with_read_tools_only():
    assert run_policy_gate(build_delegation_proposal(_task())).allowed
    writey = run_policy_gate(build_delegation_proposal(_task(tools=("Read", "Write"))))
    assert not writey.allowed                       # the worker still may not write


def test_validate_accepts_a_clean_unified_diff():
    report = validate_patch_text(GOOD_DIFF)
    assert report["passed"], report["errors"]
    assert report["files"] == ["will/core/example.py"]
    assert report["additions"] == 1 and report["deletions"] == 0
    assert parse_patch_files(GOOD_DIFF) == ["will/core/example.py"]


def test_validate_rejects_bad_patches():
    assert "patch is empty" in validate_patch_text("")["errors"][0]
    assert not validate_patch_text("just some prose, no diff markers")["passed"]

    escape = GOOD_DIFF.replace("will/core/example.py", "../outside.py")
    assert any("traverse" in e for e in validate_patch_text(escape)["errors"])

    protected = GOOD_DIFF.replace("will/core/example.py", "will.config.toml")
    assert any("protected" in e for e in validate_patch_text(protected)["errors"])

    git_dir = GOOD_DIFF.replace("will/core/example.py", ".git/hooks/post-commit")
    assert any("protected" in e for e in validate_patch_text(git_dir)["errors"])

    leaky = GOOD_DIFF.replace("# bounded by the caller", 'API_KEY = "sk_live_abcdef123456"')
    assert any("credential" in e for e in validate_patch_text(leaky)["errors"])


def test_propose_patch_via_delegation_archives_artifact(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    client = FakeDelegationClient(ok=True, summary="patch", output_text=GOOD_DIFF)

    outcome, validation, artifact = propose_patch_via_delegation(
        "add a comment", cwd="will", client=client, budget=ExistenceBudget(),
        db_path=db, directory=tmp_path / "patches",
    )

    assert validation["passed"]
    assert artifact and artifact.endswith(".patch")
    assert (tmp_path / "patches").exists()
    assert GOOD_DIFF.strip() in open(artifact).read()
    assert artifact in outcome.report.artifacts     # the reserved R1 field, now real
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.POLICY_GATE_PASSED.value in event_types
    assert EventType.DELEGATION_COMPLETED.value in event_types
    assert EventType.BUDGET_SPENT.value in event_types


def test_propose_patch_rejects_invalid_worker_output(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    client = FakeDelegationClient(ok=True, summary="oops", output_text="I could not produce a diff, sorry!")

    outcome, validation, artifact = propose_patch_via_delegation(
        "do something", cwd="will", client=client, budget=ExistenceBudget(),
        db_path=db, directory=tmp_path / "patches",
    )

    assert artifact is None
    assert not validation["passed"]
    assert not list((tmp_path / "patches").glob("*.patch")) if (tmp_path / "patches").exists() else True
