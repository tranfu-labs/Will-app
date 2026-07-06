"""Artifact references and delivery-pack manifests.

Artifacts describe durable outputs. They do not search, fetch, backtest, write
reports, or decide whether a stage advances.
"""

from will.artifacts.schemas import (
    ArtifactRef,
    BacktestRef,
    DataRef,
    DeliveryPack,
    EvidenceRef,
    SourceRef,
)

__all__ = [
    "ArtifactRef",
    "BacktestRef",
    "DataRef",
    "DeliveryPack",
    "EvidenceRef",
    "SourceRef",
]
