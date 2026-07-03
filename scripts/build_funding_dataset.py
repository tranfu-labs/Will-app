#!/usr/bin/env python3
"""Build the local append-only FundArb funding dataset and coverage report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yizhi.fundarb.dataset import main


if __name__ == "__main__":
    raise SystemExit(main())
