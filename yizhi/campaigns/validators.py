"""Deterministic artifact validators for campaign deliverables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from yizhi.campaigns.schemas import AcceptanceGate, ArtifactSpec


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_within_workspace(path: str | Path, workspace_root: str | Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(workspace_root).resolve())
        return True
    except ValueError:
        return False


def validate_artifact(
    artifact_path: str | Path,
    *,
    meta_path: str | Path,
    workspace_root: str | Path,
    spec: ArtifactSpec,
    gate: AcceptanceGate,
) -> dict[str, Any]:
    artifact = Path(artifact_path)
    meta = Path(meta_path)
    checks: list[str] = []
    errors: list[str] = []

    if not ensure_within_workspace(artifact, workspace_root) or not ensure_within_workspace(meta, workspace_root):
        errors.append("artifact paths must stay inside campaign workspace")
    else:
        checks.append("workspace_boundary")

    if gate.required_artifact and not artifact.exists():
        errors.append("artifact file is missing")
    elif artifact.exists():
        checks.append("artifact_exists")

    if not meta.exists():
        errors.append("metadata file is missing")
        metadata: dict[str, Any] = {}
    else:
        try:
            metadata = json.loads(meta.read_text())
            checks.append("metadata_json")
        except ValueError:
            errors.append("metadata file is not valid JSON")
            metadata = {}

    if metadata.get("schema") != gate.required_schema:
        errors.append(f"metadata schema must be {gate.required_schema}")
    else:
        checks.append("schema_matches")

    sections = metadata.get("sections") or []
    missing = [s for s in gate.min_sections if s not in sections]
    if missing:
        errors.append(f"missing required sections: {', '.join(missing)}")
    else:
        checks.append("required_sections")

    text = artifact.read_text(errors="ignore") if artifact.exists() else ""
    lower = text.lower()
    for pattern in gate.forbidden_patterns:
        if pattern.lower() in lower:
            errors.append(f"artifact contains forbidden pattern: {pattern}")
    if not any("forbidden pattern" in e for e in errors):
        checks.append("forbidden_patterns")

    artifact_hash = sha256_file(artifact) if artifact.exists() else ""
    if gate.require_hash and not artifact_hash:
        errors.append("artifact hash is missing")
    elif artifact_hash:
        checks.append("artifact_hash")

    return {
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "artifact_hash": artifact_hash,
        "metadata": metadata,
        "schema_name": str(metadata.get("schema", "")),
    }
