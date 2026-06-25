"""The yizhi repository as the first self-maintenance environment."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from yizhi.actions.runner import run_command
from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    EnvironmentName,
    VerificationResult,
    WillState,
    WorldObservation,
)


class SelfRepoEnvironment:
    name = EnvironmentName.SELF_REPO.value

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else Path.cwd()

    def _paper_counts(self) -> dict[str, int | None]:
        manifest_path = self.root / "data/papers/manifest.json"
        sqlite_path = self.root / "data/papers/papers.sqlite"
        manifest_count: int | None = None
        sqlite_count: int | None = None
        if manifest_path.exists():
            manifest_count = len(json.loads(manifest_path.read_text(encoding="utf-8")))
        if sqlite_path.exists():
            with sqlite3.connect(sqlite_path) as conn:
                row = conn.execute("select count(*) from papers").fetchone()
                sqlite_count = int(row[0]) if row else None
        return {"manifest_count": manifest_count, "sqlite_count": sqlite_count}

    def _git_status(self) -> str:
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return completed.stdout.strip()

    def observe(self) -> list[WorldObservation]:
        required_docs = [
            "README.md",
            "docs/what-is-will.md",
            "docs/theory-of-will.md",
            "docs/theory-of-memory.md",
            "docs/will-agent-architecture.md",
            "docs/technical-stack-rfc.md",
            "docs/evaluation-protocol.md",
        ]
        doc_status = {doc: (self.root / doc).exists() for doc in required_docs}
        counts = self._paper_counts()
        observations = [
            WorldObservation(
                environment=EnvironmentName.SELF_REPO,
                source="self_repo.required_docs",
                summary="Required yizhi doctrine documents were checked.",
                facts={"docs": doc_status, "all_present": all(doc_status.values())},
                salience=0.5,
            ),
            WorldObservation(
                environment=EnvironmentName.SELF_REPO,
                source="self_repo.paper_db",
                summary="Paper manifest and SQLite counts were checked.",
                facts={
                    **counts,
                    "expected_manifest_count": 73,
                    "paper_db_count_ok": counts["manifest_count"] == 73
                    and (counts["sqlite_count"] in (None, 73)),
                },
                salience=0.6,
            ),
            WorldObservation(
                environment=EnvironmentName.SELF_REPO,
                source="self_repo.git_status",
                summary="Repository git status was observed.",
                facts={"status": self._git_status()},
                salience=0.4,
            ),
        ]
        return observations

    def propose_actions(self, state: WillState) -> list[ActionProposal]:
        return [
            ActionProposal(
                environment=EnvironmentName.SELF_REPO,
                action_class=ActionClass.INTERNAL,
                title="Validate paper manifest JSON",
                command=["python3", "-m", "json.tool", "data/papers/manifest.json"],
                description="Parse the paper manifest without changing files.",
                dry_run=True,
            ),
            ActionProposal(
                environment=EnvironmentName.SELF_REPO,
                action_class=ActionClass.INTERNAL,
                title="Observe yizhi git status",
                command=["git", "status", "--short", "--branch"],
                description="Record local worktree state.",
                dry_run=True,
            ),
        ]

    def run(self, proposal: ActionProposal) -> ActionRecord:
        return run_command(proposal, cwd=self.root, timeout_seconds=60)

    def verify(self, record: ActionRecord) -> VerificationResult:
        passed = record.status == ActionStatus.SUCCEEDED and record.exit_code == 0
        return VerificationResult(
            action_record_id=record.id,
            passed=passed,
            checks=["exit_code_is_zero", "action_status_succeeded"],
            summary="Self repo action succeeded." if passed else "Self repo action failed.",
        )
