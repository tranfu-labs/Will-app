from yizhi.core.schemas import WillState
from yizhi.environments.self_repo import SelfRepoEnvironment


def test_self_repo_observes_docs_and_paper_db():
    env = SelfRepoEnvironment()
    observations = env.observe()
    facts = {obs.source: obs.facts for obs in observations}
    assert facts["self_repo.required_docs"]["all_present"] is True
    assert facts["self_repo.paper_db"]["manifest_count"] == 73
    assert facts["self_repo.paper_db"]["paper_db_count_ok"] is True


def test_self_repo_proposes_local_checks():
    proposals = SelfRepoEnvironment().propose_actions(WillState())
    commands = [proposal.command for proposal in proposals]
    assert ["python3", "-m", "json.tool", "data/papers/manifest.json"] in commands
    assert ["git", "status", "--short", "--branch"] in commands
