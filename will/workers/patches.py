"""Delegated patch drafting.

The worker never writes: it returns a unified diff as TEXT through the same
governed delegation chain as research (gate -> existence budget -> harness ->
secret scan). This module owns the deterministic side of the boundary:

- validate the diff structurally (real unified-diff shape, in-repo relative
  paths only, protected paths untouched, no credential material in added
  lines, bounded size);
- archive the accepted diff under `data/delegation/` as a reviewable patch
  artifact, referenced from the DelegationReport.

Nothing here applies a patch. Apply is a separate, human-gated stage.
Review with `git apply --check <artifact>` and apply manually.
"""

from __future__ import annotations

import re
from pathlib import Path

from will.core.ids import new_id
from will.core.schemas import (
    DelegationKind,
    DelegationTask,
    ExistenceBudget,
)
from will.core.secrets import contains_secret_material
from will.workers.delegation import (
    DelegationClient,
    DelegationOutcome,
    build_delegation_proposal,
    execute_delegation,
)

PATCH_DIR = Path("data/delegation")
MAX_PATCH_BYTES = 200_000
MAX_PATCH_FILES = 20

# Paths a drafted patch may never touch: VCS internals, runtime state, and the
# config/secret surface. Matched against every path the diff names.
PROTECTED_PREFIXES = (".git/", ".will/", ".env", "data/delegation/")
PROTECTED_FILES = {"will.config.toml"}

_DIFF_TARGET_RE = re.compile(r"^(?:---|\+\+\+)\s+(?:[ab]/)?(\S+)", re.MULTILINE)
_DIFF_GIT_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.MULTILINE)


def parse_patch_files(diff_text: str) -> list[str]:
    """Every repo path the diff names, deduplicated, /dev/null excluded."""
    paths: list[str] = []
    for match in _DIFF_GIT_RE.finditer(diff_text):
        paths.extend(match.groups())
    for match in _DIFF_TARGET_RE.finditer(diff_text):
        paths.append(match.group(1))
    seen: list[str] = []
    for path in paths:
        if path not in ("/dev/null",) and path not in seen:
            seen.append(path)
    return seen


def _path_reasons(path: str) -> list[str]:
    reasons: list[str] = []
    if path.startswith("/") or path.startswith("~"):
        reasons.append(f"patch path must be repo-relative: {path}")
    if ".." in Path(path).parts:
        reasons.append(f"patch path must not traverse upward: {path}")
    if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES) or path in PROTECTED_FILES:
        reasons.append(f"patch touches a protected path: {path}")
    return reasons


def validate_patch_text(diff_text: str) -> dict:
    """Deterministic structural validation of a drafted diff. Returns
    {passed, errors, files, additions, deletions}."""
    errors: list[str] = []
    text = diff_text.strip()
    if not text:
        errors.append("patch is empty")
        return {"passed": False, "errors": errors, "files": [], "additions": 0, "deletions": 0}
    if len(text.encode("utf-8")) > MAX_PATCH_BYTES:
        errors.append(f"patch exceeds {MAX_PATCH_BYTES} bytes")
    if not (_DIFF_GIT_RE.search(text) or ("--- " in text and "+++ " in text)):
        errors.append("output is not a unified diff")
    files = parse_patch_files(text)
    if not files and not errors:
        errors.append("diff names no files")
    if len(files) > MAX_PATCH_FILES:
        errors.append(f"diff touches {len(files)} files (> {MAX_PATCH_FILES})")
    for path in files:
        errors.extend(_path_reasons(path))
    added_lines = "\n".join(
        line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    if contains_secret_material(added_lines):
        errors.append("patch adds credential-shaped material")
    additions = sum(1 for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in text.splitlines() if line.startswith("-") and not line.startswith("---"))
    return {
        "passed": not errors,
        "errors": errors,
        "files": files,
        "additions": additions,
        "deletions": deletions,
    }


def save_patch_artifact(diff_text: str, *, patch_id: str | None = None, directory: str | Path | None = None) -> str:
    pid = patch_id or new_id("patch")
    path = Path(directory if directory is not None else PATCH_DIR) / f"{pid}.patch"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(diff_text.strip() + "\n")
    return str(path)


def build_patch_instruction(instruction: str) -> str:
    """The drafting contract: diff text is the only product; the worker writes
    nothing and touches nothing protected."""
    return (
        "你是受限只读的 patch 起草工人。你不能写任何文件——你输出的 diff 文本就是唯一产物。\n"
        f"目标: {instruction}\n\n"
        "硬性要求:\n"
        "1. 只输出一份标准 unified diff(git diff 格式,含 a/ b/ 前缀),不要任何其它文字、解释或代码块包裹。\n"
        "2. 所有 diff 路径以仓库根为基准(例如 a/will/core/x.py),使 `git apply` 可从仓库根直接执行。\n"
        "3. 只修改与目标直接相关的文件;不得触碰 .git/ .will/ data/delegation/ 或任何配置/密钥文件(will.config.toml 等)。\n"
        "4. diff 保持最小;不做无关重构;保持周围代码风格。\n"
        "5. 不得引入任何密钥、凭证或私有信息。"
    )


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def propose_patch_via_delegation(
    instruction: str,
    *,
    cwd: str,
    client: DelegationClient,
    budget: ExistenceBudget,
    db_path,
    directory: str | Path | None = None,
) -> tuple[DelegationOutcome, dict, str | None]:
    """One governed patch draft: gate -> budget -> harness -> secret scan ->
    deterministic diff validation -> artifact archive. Returns (delegation
    outcome, validation report, artifact path or None). Never applies."""
    task = DelegationTask(
        kind=DelegationKind.PROPOSE_PATCH,
        instruction=build_patch_instruction(instruction),
        cwd=cwd,
        allowed_tools=["Read", "Grep", "Glob"],
    )
    outcome = execute_delegation(build_delegation_proposal(task), client, budget, db_path)
    if outcome.report is None or outcome.verification is None or not outcome.verification.passed:
        return outcome, {"passed": False, "errors": ["delegation failed or was denied"], "files": [], "additions": 0, "deletions": 0}, None
    diff_text = _strip_fence(outcome.report.output_text or outcome.report.summary)
    validation = validate_patch_text(diff_text)
    if not validation["passed"]:
        return outcome, validation, None
    artifact = save_patch_artifact(diff_text, directory=directory)
    outcome.report.artifacts.append(artifact)
    return outcome, validation, artifact
