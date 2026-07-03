"""Offline tests for the opt-in LLM cognition layer.

No network and no key: the LLM path is exercised with a FakeLLMClient, and the
default-off / graceful-fallback contracts are pinned. These prove the seam works
and that the deterministic invariant holds when the engine is off.
"""

from __future__ import annotations

from yizhi.config import LLMConfig, load_llm_config
from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    EnvironmentName,
    EventType,
    LoopStatus,
    MemoryRecord,
    MemoryType,
    PolicyGateResult,
    VerificationResult,
    WillState,
    WorldObservation,
)
from yizhi.engine.llm import LiteLLMClient, OpenAILLM, load_llm, normalize_base_url
from yizhi.engine.planning import choose_proposal
from yizhi.engine.reflection import create_reflection
from yizhi.engine.thought import generate_thoughts
from yizhi.engine.findings import extract_finding, is_new_knowledge, probe_subject
from yizhi.engine.goals import generate_goal
from yizhi.core.schemas import ActionRecord, ActionStatus, Goal

_POLICY = PolicyGateResult(proposal_id="p", allowed=True, decision="allow", reasons=[])
_VERIFIED = VerificationResult(passed=True, summary="Self repo action succeeded.", checks=[])
_DETERMINISTIC_FULL = "The loop completed a bounded action and verified the result."


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        return self.payload


# --- reflection: LLM path, fallback, default-off --------------------------------

def test_reflection_uses_llm_output_when_client_provided():
    llm = FakeLLM({"content": "I verified the manifest and it held.", "learned": ["manifest stable", "trust verified state"]})
    reflection = create_reflection(
        "loop-1", _POLICY, None, _VERIFIED, LoopStatus.FULL,
        llm=llm, recalled=[MemoryRecord(kind="obs", content="prior repo reading")],
    )
    assert reflection.content == "I verified the manifest and it held."
    assert reflection.learned == ["manifest stable", "trust verified state"]
    assert llm.calls, "the LLM was called"
    # recalled memory and the outcome are grounded into the prompt
    user_prompt = llm.calls[0][1]
    assert "prior repo reading" in user_prompt
    assert "full" in user_prompt


def test_reflection_falls_back_to_deterministic_on_llm_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("network down")

    reflection = create_reflection("loop-1", _POLICY, None, _VERIFIED, LoopStatus.FULL, llm=Boom())
    assert reflection.content == _DETERMINISTIC_FULL  # degraded, did not crash


def test_reflection_signals_on_fallback_so_it_is_not_silent():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("boom-503")

    seen: list[str] = []
    reflection = create_reflection(
        "loop-1", _POLICY, None, _VERIFIED, LoopStatus.FULL, llm=Boom(),
        on_fallback=seen.append,
    )
    assert seen and "boom-503" in seen[0]          # the failure was surfaced
    assert reflection.content == _DETERMINISTIC_FULL  # and still degraded safely


def test_reflection_falls_back_when_llm_returns_no_content():
    llm = FakeLLM({"learned": ["something"]})  # malformed: missing "content"
    reflection = create_reflection("loop-1", _POLICY, None, _VERIFIED, LoopStatus.FULL, llm=llm)
    assert reflection.content == _DETERMINISTIC_FULL


def test_reflection_is_deterministic_without_an_llm():
    reflection = create_reflection("loop-1", _POLICY, None, _VERIFIED, LoopStatus.FULL)
    assert reflection.content == _DETERMINISTIC_FULL


# --- thought generation: LLM shapes action selection, with a caution floor -----

_OBS = [WorldObservation(environment=EnvironmentName.SELF_REPO, source="self_repo.x", summary="state was checked", facts={"ok": True})]
_WS = WillState()


def test_generate_thoughts_uses_llm_output_and_grounds_in_observations():
    llm = FakeLLM({"thoughts": [
        {"kind": "curiosity_gap", "content": "A gap worth a paper-safe check.", "salience": 0.8},
        {"kind": "commitment_pressure", "content": "Convert status into a bounded action.", "salience": 0.7},
    ]})
    thoughts = generate_thoughts(_OBS, _WS, memories=[], llm=llm)
    assert [t.kind for t in thoughts] == ["curiosity_gap", "commitment_pressure"]
    assert thoughts[0].content == "A gap worth a paper-safe check."
    assert thoughts[0].salience == 0.8
    assert "state was checked" in llm.calls[0][1]  # the observation grounded the prompt


def test_generate_thoughts_remaps_unknown_kind_and_clamps_salience():
    llm = FakeLLM({"thoughts": [{"kind": "world_domination", "content": "do the thing", "salience": 5.0}]})
    thoughts = generate_thoughts(_OBS, _WS, memories=[], llm=llm)
    assert thoughts[0].kind == "maintenance"  # an unknown kind can never bypass the drive vocabulary
    assert thoughts[0].salience == 1.0         # clamped into [0, 1]


def test_generate_thoughts_falls_back_and_signals_on_llm_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("engine down")

    seen: list[str] = []
    thoughts = generate_thoughts(_OBS, _WS, memories=[], llm=Boom(), on_fallback=seen.append)
    assert seen and "engine down" in seen[0]
    assert any(t.kind == "maintenance" for t in thoughts)  # deterministic still produced thoughts


def test_generate_thoughts_empty_llm_result_falls_back():
    thoughts = generate_thoughts(_OBS, _WS, memories=[], llm=FakeLLM({"thoughts": []}))
    assert thoughts  # never returns empty — fell back to deterministic


def test_caution_floor_holds_even_when_llm_omits_safety():
    # the LLM proposes only a curiosity thought, but a recalled refusal is present
    llm = FakeLLM({"thoughts": [{"kind": "curiosity_gap", "content": "explore", "salience": 0.6}]})
    refusal = MemoryRecord(kind="reflection:blocked", content="prior refusal here", memory_type=MemoryType.REFLECTIVE)
    thoughts = generate_thoughts(_OBS, _WS, memories=[refusal], llm=llm)
    assert any(t.kind == "safety_pressure" for t in thoughts)  # the deterministic floor guaranteed caution

def _arbbot_proposals():
    return [
        ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.INTERNAL,
                       title="git status", command=["git", "status", "--short", "--branch"], dry_run=True),
        ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.FINANCIAL,
                       title="dry smoke", command=["make", "smoke"], dry_run=True),
    ]


def test_choose_proposal_llm_selects_by_index():
    llm = FakeLLM({"choice": 1, "rationale": "produce paper-safe evidence"})
    chosen = choose_proposal(_arbbot_proposals(), EnvironmentName.ARBBOT, llm=llm, thoughts=[], recalled=[])
    assert chosen.title == "dry smoke"  # LLM picked index 1, not the deterministic git-status default


def test_choose_proposal_llm_out_of_range_falls_back_and_signals():
    seen: list[str] = []
    chosen = choose_proposal(_arbbot_proposals(), EnvironmentName.ARBBOT, llm=FakeLLM({"choice": 9}), on_fallback=seen.append)
    assert seen  # the bad choice was surfaced
    assert chosen.title == "git status"  # deterministic safe-internal pick


def test_choose_proposal_llm_non_integer_falls_back():
    chosen = choose_proposal(_arbbot_proposals(), EnvironmentName.ARBBOT, llm=FakeLLM({"choice": "nope"}))
    assert chosen.title == "git status"


def test_choose_proposal_llm_error_falls_back_and_signals():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("engine down")

    seen: list[str] = []
    chosen = choose_proposal(_arbbot_proposals(), EnvironmentName.ARBBOT, llm=Boom(), on_fallback=seen.append)
    assert seen and "engine down" in seen[0]
    assert chosen.title == "git status"


# --- edge-knowledge extraction: the experiment ledger -------------------------

def _scan_action():
    return ActionRecord(
        proposal_id="p", environment=EnvironmentName.ARBBOT, status=ActionStatus.SUCCEEDED,
        command=["python", "scripts/smoke_funding_diff_scan.py", "--dry-run"],
        stderr="funding_diff built sources=['binance','bybit'] eligible=['binance','bybit'] dry-run ok",
    )


def test_extract_finding_returns_grounded_knowledge():
    llm = FakeLLM({"finding": "Binance and Bybit have eligible perp+funding markets."})
    assert extract_finding(llm, _scan_action(), None) == "Binance and Bybit have eligible perp+funding markets."


def test_probe_subject_is_deterministic_per_command():
    # the same probe -> the same ledger key, so re-runs supersede instead of piling up
    s = probe_subject(["python", "scripts/smoke_funding_diff_scan.py", "--dry-run"])
    assert s == probe_subject(["python", "scripts/smoke_funding_diff_scan.py", "--dry-run"])
    assert s.startswith("arbbot/probe/") and "funding-diff" in s
    assert probe_subject(["make", "smoke"]) != s  # different probe -> different slot


def test_extract_finding_none_without_llm_or_output():
    assert extract_finding(None, _scan_action(), None) is None  # engine off
    empty = ActionRecord(proposal_id="p", environment=EnvironmentName.ARBBOT, status=ActionStatus.SUCCEEDED, command=["git", "status"])
    assert extract_finding(FakeLLM({"finding": "y"}), empty, None) is None  # nothing to mine


def test_extract_finding_empty_string_yields_no_entry():
    assert extract_finding(FakeLLM({"finding": ""}), _scan_action(), None) is None


def test_extract_finding_degrades_and_signals_on_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("extract down")

    seen: list[str] = []
    assert extract_finding(Boom(), _scan_action(), None, on_fallback=seen.append) is None
    assert seen and "extract down" in seen[0]


def test_is_new_knowledge_rewards_discovery_not_reconfirmation():
    # no prior -> new (first time this probe ran)
    assert is_new_knowledge(None, "Binance and Bybit are eligible funding-diff sources.") is True
    prior = "Binance and Bybit are eligible funding-diff sources."
    # a rephrasing of the same finding -> NOT new (high overlap; re-confirmation earns nothing)
    assert is_new_knowledge(prior, "The funding-diff sources Binance and Bybit are eligible.") is False
    # a genuinely different finding -> new (low overlap; discovery is rewarded)
    assert is_new_knowledge(prior, "Naked taker funding-diff shows negative edge under honest costs.") is True


# --- goal-genesis: yizhi sets its own goal from the ledger ----------------------

_VISION = "Advance ArbBot toward a durable, paper-safe edge by accumulating evidence."


def test_generate_goal_self_sets_from_vision_and_ledger():
    llm = FakeLLM({"title": "Probe the public funding-arb scanner", "description": "Funding-diff eligibility is known; explore the public funding-arb scan next."})
    goal = generate_goal(llm, _VISION, Goal(title="old", description="d"),
                         [("arbbot/probe/funding-diff", "Binance and Bybit are eligible.")], 100.0, 0.0)
    assert goal is not None and goal.title == "Probe the public funding-arb scanner"
    # the vision and the ledger ground the prompt
    user = llm.calls[0][1]
    assert "Advance ArbBot" in user and "funding-diff" in user


def test_generate_goal_frontier_marks_actions_explored_or_unexplored():
    # The frontier annotates each action so the agent is *told* what is still unknown,
    # rather than inferring it from opaque titles vs command-slug subjects (the gap that
    # made self-set exploration unreliable). Information, not budget pressure.
    llm = FakeLLM({"title": "Run the funding scanner", "description": "explore the unexplored funding scan"})
    frontier = [
        ("Run ArbBot offline test suite", "tests pass", True),     # established experiment
        ("Run funding diff dry-run scanner", None, True),          # UNEXPLORED experiment
        ("git status", None, False),                               # routine, not a probe
    ]
    goal = generate_goal(llm, _VISION, None, [("arbbot/probe/make-test", "tests pass")],
                         100.0, 0.0, frontier=frontier)
    assert goal is not None
    user = llm.calls[0][1]
    assert "[UNEXPLORED — no evidence yet] Run funding diff dry-run scanner" in user
    assert "[established] Run ArbBot offline test suite" in user
    assert "[routine — produces no new evidence] git status" in user


def test_generate_goal_keeps_current_goal_on_empty_title():
    # the agent decides its current goal still best advances the vision -> None (keep)
    assert generate_goal(FakeLLM({"title": "", "description": "stay the course"}), _VISION, None, [], 100.0, 0.0) is None


def test_generate_goal_none_without_llm_or_vision():
    assert generate_goal(None, _VISION, None, [], 100.0, 0.0) is None       # engine off
    assert generate_goal(FakeLLM({"title": "x"}), "", None, [], 100.0, 0.0) is None  # no vision anchor


def test_generate_goal_degrades_and_signals_on_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("goal down")

    seen: list[str] = []
    assert generate_goal(Boom(), _VISION, None, [], 100.0, 0.0, on_fallback=seen.append) is None
    assert seen and "goal down" in seen[0]


def test_load_llm_is_none_when_disabled():
    assert load_llm(LLMConfig(enabled=False, api_key="sk-x", model="gpt-5")) is None


def test_load_llm_routes_non_openai_to_litellm():
    # Multi-LLM routing: anthropic is now served NATIVELY (stdlib client, no extra
    # install); other non-openai providers still go through LiteLLMClient behind
    # the same Protocol. Construction is offline in all cases.
    from yizhi.engine.llm import AnthropicClient

    client = load_llm(LLMConfig(enabled=True, provider="anthropic", api_key="sk-x", model="claude-sonnet-4-6"))
    assert isinstance(client, AnthropicClient)
    gem_client = load_llm(LLMConfig(enabled=True, provider="gemini", api_key="k", model="gemini-3-flash"))
    assert isinstance(gem_client, LiteLLMClient)
    assert gem_client._model_id() == "gemini/gemini-3-flash"            # provider/model
    # a fully-qualified id is respected as-is
    gem = LiteLLMClient(LLMConfig(enabled=True, provider="gemini", model="gemini/gemini-3-flash"))
    assert gem._model_id() == "gemini/gemini-3-flash"
    # still off by default / openai still routes to the direct client
    assert load_llm(LLMConfig(enabled=False, provider="anthropic", model="x")) is None
    assert isinstance(load_llm(LLMConfig(enabled=True, provider="openai", api_key="sk-x", model="gpt-5")), OpenAILLM)


def test_load_llm_is_none_without_a_key():
    assert load_llm(LLMConfig(enabled=True, api_key="", model="gpt-5")) is None


def test_openai_client_carries_request_timeout():
    # Regression: a hung proxy call once blocked the loop for an hour (no timeout).
    # The client must carry a wall-clock cap so a stuck call raises -> deterministic fallback.
    from yizhi.engine.llm import OpenAILLM

    client = OpenAILLM(LLMConfig(enabled=True, api_key="sk-test", model="gpt-x", request_timeout=12.5))._client()
    assert client.timeout == 12.5
    assert client.max_retries == 2


def test_load_llm_returns_openai_client_when_active():
    client = load_llm(LLMConfig(enabled=True, provider="openai", api_key="sk-x", model="gpt-5"))
    assert isinstance(client, OpenAILLM)  # constructed, but no openai import / call yet


def test_load_llm_non_openai_now_served_by_litellm():
    # Was: non-openai providers returned None, then all went to LiteLLM. Now:
    # anthropic is native; the LiteLLM path remains for everything else.
    from yizhi.engine.llm import AnthropicClient

    assert isinstance(load_llm(LLMConfig(enabled=True, provider="anthropic", api_key="sk-x", model="m")), AnthropicClient)
    assert isinstance(load_llm(LLMConfig(enabled=True, provider="ollama", api_key="k", model="m")), LiteLLMClient)


def test_config_defaults_disabled_when_file_absent(tmp_path):
    cfg = load_llm_config(tmp_path / "absent.toml")
    assert cfg.enabled is False and cfg.active is False


def test_config_reads_toml_file(tmp_path, monkeypatch):
    monkeypatch.delenv("YIZHI_LLM_ENABLED", raising=False)  # let the file's value stand
    path = tmp_path / "will.config.toml"
    path.write_text('[llm]\nenabled = true\nprovider = "openai"\napi_key = "sk-file"\nmodel = "gpt-file"\n', encoding="utf-8")
    cfg = load_llm_config(path)
    assert cfg.active and cfg.api_key == "sk-file" and cfg.model == "gpt-file"


def test_config_env_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setenv("YIZHI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("YIZHI_LLM_MODEL", "gpt-env")
    cfg = load_llm_config(tmp_path / "absent.toml")
    assert cfg.active and cfg.api_key == "sk-env" and cfg.model == "gpt-env"


def test_loop_emits_llm_fallback_event_when_engine_fails(tmp_path, monkeypatch):
    # A failing LLM injected into the loop must surface an auditable event and
    # still complete (deterministic) — no silent always-deterministic run.
    from yizhi.engine import loop as loop_module
    from yizhi.engine.loop import run_step
    from yizhi.environments.self_repo import SelfRepoEnvironment
    from yizhi.core.schemas import WillState
    from yizhi.state.store import list_events

    class FailingLLM:
        def complete_json(self, system, user):
            raise RuntimeError("simulated engine outage")

    monkeypatch.setattr(loop_module, "load_llm", lambda: FailingLLM())
    db = tmp_path / "state.sqlite"
    result = run_step(SelfRepoEnvironment(), WillState(), db)

    types = {e["type"] for e in list_events(correlation_id=result.loop.id, path=db)}
    assert EventType.LLM_FALLBACK.value in types        # the degradation is visible
    assert EventType.REFLECTION_CREATED.value in types  # and the loop still finished


def test_normalize_base_url_appends_v1_only_when_no_path():
    # bare host -> /v1 (OpenAI-compatible proxies serve under /v1)
    assert normalize_base_url("https://proxy.example.com/") == "https://proxy.example.com/v1"
    assert normalize_base_url("https://proxy.example.com") == "https://proxy.example.com/v1"
    # explicit path respected, empty passthrough
    assert normalize_base_url("https://proxy.example.com/v1") == "https://proxy.example.com/v1"
    assert normalize_base_url("https://proxy.example.com/api") == "https://proxy.example.com/api"
    assert normalize_base_url("") == ""
