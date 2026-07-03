from __future__ import annotations

from pathlib import Path

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.engine import campaign_tick, revisit_stage
from yizhi.campaigns.schemas import CampaignStatus, StageStatus
from yizhi.campaigns.store import load_campaign, save_campaign_started
from yizhi.campaigns.validators import validate_artifact
from yizhi.core.schemas import EventType
from yizhi.state.store import list_events


def test_btc_campaign_template_has_s1_to_s4(tmp_path):
    campaign = build_btc_campaign(workspace_root=tmp_path)
    assert campaign.title == "BTC Research Campaign MVP"
    assert [s.id for s in campaign.stages] == ["S1", "S2", "S3", "S4"]
    assert campaign.stages[0].artifact_spec.schema_name == "btc_principles_report_v1"
    assert campaign.budget.max_stages == 4


def test_campaign_tick_accepts_s1_and_advances_to_s2(tmp_path):
    db = tmp_path / "state.sqlite"
    campaign = build_btc_campaign(campaign_id="btc-test", workspace_root=tmp_path / "campaigns")
    save_campaign_started(db, campaign)

    result = campaign_tick(db, campaign)

    assert result.status == "advanced"
    assert result.stage_id == "S1"
    assert result.deliverable_id
    assert campaign.cursor == 1
    assert campaign.stages[0].status == StageStatus.ACCEPTED
    assert campaign.stages[0].deliverable_id == result.deliverable_id
    assert list(Path(campaign.workspace_root, "S1").glob("*/S1_btc_principles.md"))
    event_types = [e["type"] for e in list_events(path=db)]
    assert EventType.CAMPAIGN_STAGE_STARTED.value in event_types
    assert EventType.TASKRUN_REQUESTED.value in event_types
    assert EventType.TASKRUN_COMPLETED.value in event_types
    assert EventType.DELIVERABLE_ACCEPTED.value in event_types
    assert EventType.CAMPAIGN_STAGE_ADVANCED.value in event_types


def test_campaign_run_can_complete_all_fake_stages(tmp_path):
    db = tmp_path / "state.sqlite"
    campaign = build_btc_campaign(campaign_id="btc-test", workspace_root=tmp_path / "campaigns")
    save_campaign_started(db, campaign)

    for _ in range(4):
        result = campaign_tick(db, campaign)

    assert result.status == "completed"
    assert campaign.status == CampaignStatus.COMPLETED
    assert campaign.cursor == 4
    assert all(stage.status == StageStatus.ACCEPTED for stage in campaign.stages)
    assert EventType.CAMPAIGN_COMPLETED.value in {e["type"] for e in list_events(path=db)}


def test_revisit_stage_supersedes_old_deliverable_and_rewinds_cursor(tmp_path):
    db = tmp_path / "state.sqlite"
    campaign = build_btc_campaign(campaign_id="btc-test", workspace_root=tmp_path / "campaigns")
    save_campaign_started(db, campaign)
    first = campaign_tick(db, campaign)
    old_deliverable = first.deliverable_id

    revisit_stage(db, campaign, stage_id="S1", note="补充调研资金费率机制")

    assert campaign.cursor == 0
    assert campaign.status == CampaignStatus.ACTIVE
    assert campaign.stages[0].status == StageStatus.PENDING
    assert campaign.stages[0].deliverable_id is None
    assert "补充调研资金费率机制" in campaign.stages[0].revision_notes
    assert "补充调研资金费率机制" not in campaign.stages[1].revision_notes
    events = list_events(path=db)
    supersede_events = [e for e in events if e["type"] == EventType.DELIVERABLE_SUPERSEDED.value]
    assert supersede_events
    assert supersede_events[0]["payload"]["old_deliverable_id"] == old_deliverable

    second = campaign_tick(db, campaign)
    assert second.status == "advanced"
    assert second.deliverable_id != old_deliverable
    produced = sorted(Path(second.campaign.workspace_root, "S1").glob("*/S1_btc_principles.md"))
    assert len(produced) == 2
    new_artifact = Path(second.campaign.workspace_root, "S1", second.task_run_id, "S1_btc_principles.md")
    assert new_artifact.exists()
    assert "补充调研资金费率机制" in new_artifact.read_text()


def test_validator_rejects_artifact_outside_workspace(tmp_path):
    campaign = build_btc_campaign(campaign_id="btc-test", workspace_root=tmp_path / "campaigns")
    stage = campaign.stages[0]
    outside = tmp_path / "outside.md"
    outside_meta = tmp_path / "outside.meta.json"
    outside.write_text("hello")
    outside_meta.write_text('{"schema":"btc_principles_report_v1","sections":[]}')

    result = validate_artifact(
        outside,
        meta_path=outside_meta,
        workspace_root=campaign.workspace_root,
        spec=stage.artifact_spec,
        gate=stage.acceptance_gate,
    )

    assert not result["passed"]
    assert any("workspace" in error for error in result["errors"])


def test_load_campaign_projects_latest_state(tmp_path):
    db = tmp_path / "state.sqlite"
    campaign = build_btc_campaign(campaign_id="btc-test", workspace_root=tmp_path / "campaigns")
    save_campaign_started(db, campaign)
    campaign_tick(db, campaign)

    loaded = load_campaign(db, "btc-test")

    assert loaded is not None
    assert loaded.cursor == 1
    assert loaded.stages[0].status == StageStatus.ACCEPTED


def test_cli_campaign_create_run_state_revisit(tmp_path, capsys):
    from yizhi.cli import main

    db = tmp_path / "state.sqlite"
    root = tmp_path / "campaigns"
    assert main(["--db", str(db), "campaign", "create-btc", "--id", "btc-cli", "--workspace-root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "campaign_id: btc-cli" in out

    assert main(["--db", str(db), "campaign", "run", "--id", "btc-cli", "--max-ticks", "2"]) == 0
    out = capsys.readouterr().out
    assert "last_tick: advanced" in out
    assert "cursor: 2" in out

    assert main(["--db", str(db), "campaign", "state", "--id", "btc-cli"]) == 0
    out = capsys.readouterr().out
    assert '"id": "btc-cli"' in out
    assert '"cursor": 2' in out

    assert main([
        "--db", str(db), "campaign", "revisit", "--id", "btc-cli",
        "--stage", "S1", "--note", "补充调研资金费率机制",
    ]) == 0
    out = capsys.readouterr().out
    assert "cursor: 0" in out
