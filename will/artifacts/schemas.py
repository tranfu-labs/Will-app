"""Schemas for durable artifact and evidence references."""

from __future__ import annotations

from pydantic import Field

from will.core.ids import new_id
from will.core.schemas import WillModel
from will.core.time import utc_now_iso


class ArtifactRef(WillModel):
    id: str = Field(default_factory=lambda: new_id("artifact"))
    kind: str
    path: str
    schema_name: str = ""
    content_hash: str = ""
    produced_by: str = ""
    stage_id: str = ""
    task_run_id: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class SourceRef(WillModel):
    id: str = Field(default_factory=lambda: new_id("source"))
    uri: str
    title: str = ""
    provider: str = ""
    retrieved_at: str = Field(default_factory=utc_now_iso)
    content_hash: str = ""
    license: str = ""


class EvidenceRef(WillModel):
    id: str = Field(default_factory=lambda: new_id("evidence"))
    source_ref_id: str
    claim_id: str = ""
    locator: str = ""
    snippet_hash: str = ""
    grade: str = "ungraded"


class DataRef(WillModel):
    id: str = Field(default_factory=lambda: new_id("data"))
    path: str
    provider: str = ""
    symbol: str = ""
    time_range: str = ""
    frequency: str = ""
    schema_name: str = ""
    content_hash: str = ""
    quality_report_ref: str = ""


class BacktestRef(WillModel):
    id: str = Field(default_factory=lambda: new_id("backtest"))
    strategy_id: str
    data_ref_id: str
    params_hash: str = ""
    metrics_path: str = ""
    content_hash: str = ""


class DeliveryPack(WillModel):
    id: str = Field(default_factory=lambda: new_id("delivery-pack"))
    title: str
    final_answer_ref: str = ""
    accepted_artifact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    data_refs: list[str] = Field(default_factory=list)
    backtest_refs: list[str] = Field(default_factory=list)
    lens_report_refs: list[str] = Field(default_factory=list)
    decision_event_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    manifest_hash: str = ""
