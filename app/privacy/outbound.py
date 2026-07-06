from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

from app.privacy.policy import is_opaque_reference, validate_artifact

if TYPE_CHECKING:
    from app.models.audit import AuditFinding
    from app.models.normalized import NormalizedAccount


_ALLOWED_TOP_LEVEL = {"schema_version", "privacy_mode", "account_metrics", "boards"}
_ALLOWED_ACCOUNT_METRICS = {"workspace_count", "board_count"}
_ALLOWED_BOARD = {
    "board_ref",
    "workspace_ref",
    "group_count",
    "sample_item_count",
    "column_type_counts",
    "findings",
}
_ALLOWED_FINDING = {"rule_id", "severity", "object_type"}


def build_technical_analysis_payload(
    model: NormalizedAccount, findings: list[AuditFinding]
) -> dict[str, Any]:
    findings_by_board: dict[str, list[AuditFinding]] = defaultdict(list)
    for finding in findings:
        findings_by_board[finding.object_id].append(finding)
    return {
        "schema_version": "1.0",
        "privacy_mode": "technical_metadata_only",
        "account_metrics": {
            "workspace_count": len(model.workspaces),
            "board_count": len(model.boards),
        },
        "boards": [
            {
                "board_ref": board.id,
                "workspace_ref": board.workspace_id,
                "group_count": len(board.groups),
                "sample_item_count": board.item_count,
                "column_type_counts": dict(Counter(c.normalized_type for c in board.columns)),
                "findings": [
                    {
                        "rule_id": finding.rule_id,
                        "severity": finding.severity,
                        "object_type": finding.object_type,
                    }
                    for finding in findings_by_board.get(board.id, [])
                ],
            }
            for board in model.boards
        ],
    }


def validate_outbound_payload(payload: dict[str, Any]) -> None:
    validate_artifact(payload)
    if set(payload) != _ALLOWED_TOP_LEVEL:
        raise ValueError("Outbound payload contains unexpected top-level fields")
    if set(payload["account_metrics"]) != _ALLOWED_ACCOUNT_METRICS:
        raise ValueError("Outbound account metrics contain unexpected fields")
    for board in payload["boards"]:
        if set(board) != _ALLOWED_BOARD:
            raise ValueError("Outbound board payload contains unexpected fields")
        if not is_opaque_reference(board["board_ref"], "board"):
            raise ValueError("Outbound board reference is not pseudonymous")
        if board["workspace_ref"] is not None and not is_opaque_reference(board["workspace_ref"], "workspace"):
            raise ValueError("Outbound workspace reference is not pseudonymous")
        for finding in board["findings"]:
            if set(finding) != _ALLOWED_FINDING:
                raise ValueError("Outbound finding contains unexpected fields")
