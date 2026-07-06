from __future__ import annotations

from app.models.audit import AuditFinding
from app.models.normalized import NormalizedAccount, NormalizedBoard


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
    return findings
