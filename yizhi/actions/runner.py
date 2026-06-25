"""Bounded subprocess runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

from yizhi.core.schemas import ActionProposal, ActionRecord, ActionStatus


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def run_command(proposal: ActionProposal, cwd: Path, timeout_seconds: int = 120) -> ActionRecord:
    if not proposal.command:
        return ActionRecord(
            proposal_id=proposal.id,
            environment=proposal.environment,
            status=ActionStatus.FAILED,
            command=[],
            error="proposal has no command",
        )
    try:
        completed = subprocess.run(
            proposal.command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - exercised by integration failure paths
        return ActionRecord(
            proposal_id=proposal.id,
            environment=proposal.environment,
            status=ActionStatus.FAILED,
            command=proposal.command,
            error=str(exc),
        )
    return ActionRecord(
        proposal_id=proposal.id,
        environment=proposal.environment,
        status=ActionStatus.SUCCEEDED if completed.returncode == 0 else ActionStatus.FAILED,
        command=proposal.command,
        exit_code=completed.returncode,
        stdout=_truncate(completed.stdout),
        stderr=_truncate(completed.stderr),
    )
