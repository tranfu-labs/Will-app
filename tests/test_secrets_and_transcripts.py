from __future__ import annotations

from yizhi.campaigns.executor import strip_code_fence
from yizhi.core.secrets import contains_secret_material
from yizhi.execution.delegation import archive_transcript


def test_secret_scan_catches_credential_shapes():
    assert contains_secret_material("config had APIKEY=abc12345 in it")
    assert contains_secret_material("api_key: 'sk-live-0123456789'")
    assert contains_secret_material("-----BEGIN RSA PRIVATE KEY-----")
    assert contains_secret_material("aws AKIAIOSFODNN7EXAMPLE id")


def test_secret_scan_allows_legitimate_research_prose():
    # The exact phrases that killed research artifacts under the bare-keyword scan.
    assert not contains_secret_material("交易所的 API secret 管理与轮换策略值得调研。")
    assert not contains_secret_material("private key loss is irreversible for self-custody users")
    assert not contains_secret_material("the token economics of BTC do not include staking")


def test_strip_code_fence_unwraps_whole_document():
    fenced = "```markdown\n# 报告\n\n## summary\n\n正文\n```"
    assert strip_code_fence(fenced).startswith("# 报告")
    plain = "# 报告\n\n```python\nx = 1\n```\n\n尾注"
    assert strip_code_fence(plain) == plain  # inner fences untouched


def test_archive_transcript_writes_and_survives_failure(tmp_path):
    ref = archive_transcript("task-1", "stdout text", "stderr text", root=tmp_path)
    assert ref
    content = (tmp_path / ".yizhi/delegation-transcripts/task-1.txt").read_text()
    assert "stdout text" in content and "stderr text" in content
    # Unwritable root degrades to "" instead of raising.
    assert archive_transcript("task-2", "a", "b", root=tmp_path / "no" / "such" / "\0bad") == ""
