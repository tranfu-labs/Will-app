"""Deterministic secret-material scanner shared by delegation and campaign gates.

Bare keywords ("secret", "private key") false-positive on legitimate research
text — a venue report that says "API secret management" or "private key loss is
irreversible" is not a leak. What we actually refuse to pass through the will's
verification is *credential material*: an assignment of a key-like name to a
value, a PEM block, or a well-known key shape.
"""

from __future__ import annotations

import re

_SECRET_PATTERNS = [
    # name = value / name: value where the name is credential-like and the
    # value is a token of meaningful length (rules out prose like "secret 管理").
    re.compile(r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password|private[_-]?key)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+.]{6,}"),
    # PEM-encoded key blocks.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"-----BEGIN"),
    # AWS-style access key ids.
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)
