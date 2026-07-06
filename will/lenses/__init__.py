"""Will's quality-lens seam.

Soul is an external, read-only methodology/evidence/risk lens. This package
owns only the contract (`SoulLensReport`, the `SoulLens` protocol) and a deterministic offline
implementation (`FakeSoulLens`). A real Soul API plugs in behind the same seam.
"""

from __future__ import annotations

from will.lenses.fake import FakeSoulLens
from will.lenses.schemas import Severity, SoulLens, SoulLensReport

__all__ = [
    "SoulLens",
    "SoulLensReport",
    "Severity",
    "FakeSoulLens",
]
