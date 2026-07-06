"""Test-suite guards.

Force optional provider-backed adapters OFF for the whole test run, regardless of any
local `will.config.toml` the developer may have enabled. This keeps the suite
fully deterministic and offline (no network, no key) — the project's invariant.
Live LLM behaviour is verified outside pytest. Tests that exercise config/env
logic use monkeypatch and override this per-test as needed.
"""

import os

os.environ["WILL_LLM_ENABLED"] = "0"
# The offline suite must never start a real coding-harness subprocess, even
# when the developer's local config has the delegation gate open.
os.environ["WILL_DELEGATION_ENABLED"] = "0"
