from __future__ import annotations

from yizhi.core.schemas import DelegationKind, DelegationTask, EventType, ExistenceBudget
from yizhi.engine.delegation import FakeDelegationClient, build_delegation_proposal
from yizhi.engine.patches import (
    parse_patch_files,
    propose_patch_via_delegation,
    validate_patch_text,
)
from yizhi.policy.gates import run_policy_gate
from yizhi.state.store import init_db, list_events

GOOD_DIFF = """\
diff --git a/yizhi/core/example.py b/yizhi/core/example.py
--- a/yizhi/core/example.py
+++ b/yizhi/core/example.py
@@ -1,3 +1,4 @@
 def f():
+    # bounded by the caller
     return 1
"""


def _task(kind=DelegationKind.PROPOSE_PATCH, tools=("Read", "Grep", "Glob")):
    return DelegationTask(kind=kind, instruction="draft", cwd="yizhi", allowed_tools=list(tools))


def test_gate_allows_propose_patch_with_read_tools_only():
    assert run_policy_gate(build_delegation_proposal(_task())).allowed
    writey = run_policy_gate(build_delegation_proposal(_task(tools=("Read", "Write"))))
    assert not writey.allowed                       # the worker still may not write


def test_validate_accepts_a_clean_unified_diff():
    report = validate_patch_text(GOOD_DIFF)
    assert report["passed"], report["errors"]
    assert report["files"] == ["yizhi/core/example.py"]
    assert report["additions"] == 1 and report["deletions"] == 0
    assert parse_patch_files(GOOD_DIFF) == ["yizhi/core/example.py"]


def test_validate_rejects_bad_patches():
    assert "patch is empty" in validate_patch_text("")["errors"][0]
    assert not validate_patch_text("just some prose, no diff markers")["passed"]

    escape = GOOD_DIFF.replace("yizhi/core/example.py", "../outside.py")
    assert any("traverse" in e for e in validate_patch_text(escape)["errors"])

    protected = GOOD_DIFF.replace("yizhi/core/example.py", "will.config.toml")
    assert any("protected" in e for e in validate_patch_text(protected)["errors"])

    git_dir = GOOD_DIFF.replace("yizhi/core/example.py", ".git/hooks/post-commit")
    assert any("protected" in e for e in validate_patch_text(git_dir)["errors"])

    leaky = GOOD_DIFF.replace("# bounded by the caller", 'API_KEY = "sk_live_abcdef123456"')
    assert any("credential" in e for e in validate_patch_text(leaky)["errors"])


def test_propose_patch_via_delegation_archives_artifact(tmp_path):
    db = init_db(tmp_path / "s.sqlite")
    client = FakeDelegationClient(ok=True, summary="patch", output_text=GOOD_DIFF)

    outcome, validation, artifact = propose_patch_via_delegation(
        "add a comment", cwd="yizhi", client=client, budget=ExistenceBudget(),
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
        "do something", cwd="yizhi", client=client, budget=ExistenceBudget(),
        db_path=db, directory=tmp_path / "patches",
    )

    assert artifact is None
    assert not validation["passed"]
    assert not list((tmp_path / "patches").glob("*.patch")) if (tmp_path / "patches").exists() else True


def test_chat_patch_command_drafts_through_governance(tmp_path, monkeypatch):
    import yizhi.engine.patches as patches_module
    from yizhi.liaison.chat import ChatIO, run_chat

    monkeypatch.setattr(patches_module, "PATCH_DIR", tmp_path / "patches")
    db = init_db(tmp_path / "s.sqlite")
    client = FakeDelegationClient(ok=True, summary="patch", output_text=GOOD_DIFF)
    feed = iter(["/patch 给 example.py 加注释", "/quit"])
    io = ChatIO(input_fn=lambda p: next(feed), output_fn=lambda t: None)

    run_chat(db, io=io, llm=None, delegation_client=client, max_turns=5)

    assert client.called
    assert client.last_task.kind == "propose_patch"
    assert any("patch 已起草" in t for t in io.transcript)
    assert any("git apply --check" in t for t in io.transcript)
    assert list((tmp_path / "patches").glob("*.patch"))
