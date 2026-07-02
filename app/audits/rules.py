from __future__ import annotations

from collections import Counter, defaultdict

from app.models.audit import AuditFinding
from app.models.normalized import NormalizedAccount, NormalizedBoard


def finding(rule_id, severity, board: NormalizedBoard, text, evidence, rec, object_type="board", object_id=None, object_name=None):
    return AuditFinding(rule_id=rule_id, severity=severity, object_type=object_type, object_id=object_id or board.id, object_name=object_name or board.name, finding=text, evidence=evidence, recommendation=rec)


def audit_model(model: NormalizedAccount) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    name_counts = Counter(b.name.strip().lower() for b in model.boards if b.name.strip())
    status_labels_by_board: dict[str, set[str]] = defaultdict(set)
    for b in model.boards:
        title_types = [(c.title.lower(), c.normalized_type) for c in b.columns]
        names = [c.title.lower() for c in b.columns]
        if not any(t == "people" or "owner" in n or "assignee" in n for n, t in title_types):
            findings.append(finding("missing_owner_column", "medium", b, "Board has no obvious owner or assignee column.", {"columns": names}, "Add or identify a single accountable owner field before migration."))
        if not any(t in {"date", "timeline"} or "due" in n or "deadline" in n for n, t in title_types):
            findings.append(finding("missing_due_date_column", "medium", b, "Board has no obvious due date or timeline column.", {"columns": names}, "Add a due date/timeline field for task scheduling semantics."))
        if not any(t == "status" for _, t in title_types):
            findings.append(finding("missing_status_column", "high", b, "Board has no status column.", {"column_types": [c.normalized_type for c in b.columns]}, "Define a status workflow before mapping to ClickUp statuses."))
        if len(b.name.strip()) < 4 or b.name.lower().strip() in {"test", "new board", "board", "main"}:
            findings.append(finding("unclear_board_name", "low", b, "Board name is generic or unclear.", {"name": b.name}, "Rename with a business process noun before migration."))
        if name_counts[b.name.strip().lower()] > 1:
            findings.append(finding("duplicate_board_name", "medium", b, "Multiple boards share the same name.", {"name": b.name, "count": name_counts[b.name.strip().lower()]}, "Disambiguate board names before migration."))
        text_cols = [c.title for c in b.columns if c.normalized_type == "text"]
        if len(text_cols) > 8:
            findings.append(finding("too_many_text_columns", "medium", b, "Board has many free-text columns.", {"text_columns": text_cols}, "Convert repeated text semantics into typed fields where possible."))
        dup_cols = [name for name, count in Counter(names).items() if count > 1 and name]
        if dup_cols:
            findings.append(finding("duplicate_column_titles", "medium", b, "Board has duplicate column titles.", {"duplicate_titles": dup_cols}, "Rename duplicate columns to preserve field meaning."))
        for c in b.columns:
            if c.normalized_type == "formula":
                findings.append(finding("formula_risk", "high", b, "Formula column may not migrate directly.", {"column_id": c.id, "title": c.title}, "Document formula logic and rebuild or materialize values.", "column", c.id, c.title))
            if c.normalized_type == "mirror":
                findings.append(finding("mirror_column_risk", "high", b, "Mirror column requires relationship/reporting redesign.", {"column_id": c.id, "title": c.title}, "Plan a ClickUp rollup/reporting workaround.", "column", c.id, c.title))
            if c.normalized_type == "connect_board" and len(c.relationship_targets) > 1:
                findings.append(finding("connect_board_complexity", "high", b, "Connect Board column targets multiple boards.", {"column_id": c.id, "targets": c.relationship_targets}, "Review linked-task or relationship mapping manually.", "column", c.id, c.title))
            if c.normalized_type == "status":
                status_labels_by_board[b.id].update(label.lower() for label in c.labels if label)
        if len(b.groups) > 20:
            findings.append(finding("too_many_groups", "medium", b, "Board has many groups.", {"group_count": len(b.groups)}, "Decide whether groups should become Lists, statuses, or sections."))
        lname = b.name.lower()
        if "archive" in lname or "old" in lname:
            findings.append(finding("archive_board_smell", "low", b, "Board appears archival or stale.", {"name": b.name}, "Consider excluding or archiving instead of migrating."))
        if "copy" in lname or "duplicate" in lname:
            findings.append(finding("board_copy_smell", "low", b, "Board appears to be a copy.", {"name": b.name}, "Confirm whether this is canonical before migration."))
        if len(b.columns) < 3 or not b.groups:
            findings.append(finding("low_schema_quality", "medium", b, "Board schema is sparse or incomplete.", {"column_count": len(b.columns), "group_count": len(b.groups)}, "Review whether this board represents a real workflow."))
    label_sets = list(status_labels_by_board.values())
    if len(label_sets) > 1:
        common = set.intersection(*label_sets) if all(label_sets) else set()
        for b in model.boards:
            labels = status_labels_by_board.get(b.id, set())
            if labels and common and len(labels - common) > 4:
                findings.append(finding("status_label_drift", "medium", b, "Status labels differ substantially from other boards.", {"labels": sorted(labels), "common_labels": sorted(common)}, "Standardize status vocabularies before migration."))
    return findings
