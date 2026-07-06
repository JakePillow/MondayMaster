from __future__ import annotations

from app.models.audit import AuditFinding
from app.models.normalized import NormalizedAccount, NormalizedBoard

MEGA_BOARD_ITEM_THRESHOLD = 500
GOVERNANCE_LOCK_RATIO_THRESHOLD = 0.7


def finding(rule_id, severity, board: NormalizedBoard, text, evidence, rec, object_type="board", object_id=None, object_name=None):
    return AuditFinding(rule_id=rule_id, severity=severity, object_type=object_type, object_id=object_id or board.id, object_name=object_name or board.name, finding=text, evidence=evidence, recommendation=rec)


def audit_model(model: NormalizedAccount) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for b in model.boards:
        title_types = [(c.title.lower(), c.normalized_type) for c in b.columns]
        names = [c.title.lower() for c in b.columns]
        if not any(t == "people" for _, t in title_types):
            findings.append(finding("missing_owner_column", "medium", b, "Board has no obvious owner or assignee column.", {"columns": names}, "Add or identify a single accountable owner field before migration."))
        if not any(t in {"date", "timeline"} for _, t in title_types):
            findings.append(finding("missing_due_date_column", "medium", b, "Board has no obvious due date or timeline column.", {"columns": names}, "Add a due date/timeline field for task scheduling semantics."))
        if not any(t == "status" for _, t in title_types):
            findings.append(finding("missing_status_column", "high", b, "Board has no status column.", {"column_types": [c.normalized_type for c in b.columns]}, "Define a status workflow before mapping to ClickUp statuses."))
        text_cols = [c.title for c in b.columns if c.normalized_type == "text"]
        if len(text_cols) > 8:
            findings.append(finding("too_many_text_columns", "medium", b, "Board has many free-text columns.", {"text_columns": text_cols}, "Convert repeated text semantics into typed fields where possible."))
        for c in b.columns:
            if c.normalized_type == "formula":
                findings.append(finding("formula_risk", "high", b, "Formula column may not migrate directly.", {"column_id": c.id, "title": c.title}, "Document formula logic and rebuild or materialize values.", "column", c.id, c.title))
            if c.normalized_type == "mirror":
                findings.append(finding("mirror_column_risk", "high", b, "Mirror column requires relationship/reporting redesign.", {"column_id": c.id, "title": c.title}, "Plan a ClickUp rollup/reporting workaround.", "column", c.id, c.title))
            if c.normalized_type == "connect_board":
                findings.append(finding("connect_board_complexity", "high", b, "Connect Board relationship requires manual mapping review.", {"column_id": c.id}, "Review linked-task or relationship mapping manually without exporting relationship content.", "column", c.id, c.title))
        if len(b.groups) > 20:
            findings.append(finding("too_many_groups", "medium", b, "Board has many groups.", {"group_count": len(b.groups)}, "Decide whether groups should become Lists, statuses, or sections."))
        if len(b.columns) < 3 or not b.groups:
            findings.append(finding("low_schema_quality", "medium", b, "Board schema is sparse or incomplete.", {"column_count": len(b.columns), "group_count": len(b.groups)}, "Review whether this board represents a real workflow."))
        if len(b.groups) == 1 and b.groups[0].item_count > MEGA_BOARD_ITEM_THRESHOLD:
            g = b.groups[0]
            findings.append(finding("single_group_mega_board", "medium", b, f"Board has {g.item_count} items in a single flat group.", {"group_id": g.id, "item_count": g.item_count, "threshold": MEGA_BOARD_ITEM_THRESHOLD}, "Consider archiving or sub-grouping (e.g. by year or status) before migration to keep the destination List manageable."))
        if b.columns:
            locked_count = sum(1 for c in b.columns if c.is_locked)
            locked_ratio = locked_count / len(b.columns)
            if locked_ratio >= GOVERNANCE_LOCK_RATIO_THRESHOLD:
                findings.append(finding("governance_signal_locked_columns", "low", b, f"{locked_count}/{len(b.columns)} columns are locked ({locked_ratio:.0%}). Indicates intentional schema governance.", {"locked_count": locked_count, "total_columns": len(b.columns), "locked_ratio": round(locked_ratio, 4)}, "Treat as a low-risk board for migration; use as a reference pattern when auditing less-disciplined boards elsewhere in the account."))
        for a in b.automations:
            if a.is_cross_board:
                findings.append(finding("cross_board_automation_trigger", "high", b, f"Automation ({a.trigger_type.value} → {a.action_type.value}) creates/modifies items on a different board ('{a.target_board_name or a.target_board_id}').", {"target_board_id": a.target_board_id, "trigger_type": a.trigger_type.value, "action_type": a.action_type.value}, "ClickUp has no direct equivalent for cross-board automation triggers; rebuild this logic manually rather than auto-mapping it.", "automation"))
    return findings
