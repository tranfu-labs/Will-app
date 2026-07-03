"""Test-suite guards.

Force the LLM cognition engine OFF for the whole test run, regardless of any
local `will.config.toml` or legacy `yizhi.config.toml` the developer may have enabled. This keeps the suite
fully deterministic and offline (no network, no key) — the project's invariant.
Live LLM behaviour is verified outside pytest. Tests that exercise config/env
logic use monkeypatch and override this per-test as needed.
"""

import os

os.environ["YIZHI_LLM_ENABLED"] = "0"
os.environ["YIZHI_EMBEDDING_ENABLED"] = "0"
