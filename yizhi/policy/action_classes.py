"""Action class helpers."""

from __future__ import annotations

from yizhi.core.schemas import ActionClass

HIGH_RISK_ACTION_CLASSES = {
    ActionClass.FINANCIAL,
    ActionClass.CREDENTIAL,
    ActionClass.EXTERNAL_WRITE,
    ActionClass.SELF_MODIFY,
    ActionClass.REPRODUCE,
}
