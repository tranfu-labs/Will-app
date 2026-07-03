#!/usr/bin/env python3
"""Build the FundArb promotion/kill packet from experiment results."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yizhi.fundarb.packets import main


if __name__ == "__main__":
    raise SystemExit(main())
