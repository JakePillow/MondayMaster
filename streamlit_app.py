"""Local Streamlit dashboard for MondayMaster audit runs.

Purely a viewer: it reads the JSON artefacts already written by the CLI
(`normalise` + `audit`) and never talks to monday.com or mutates anything.
Run with:

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.models.audit import AuditFinding, AuditResult
from app.models.normalised import NormalisedAccount

SEVERITY_ORDER = ["critical", "high", "medium", "low"]
SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


def load_run(export_root: Path) -> tuple[NormalisedAccount | None, AuditResult | None]:
    """Load a normalised schema + audit findings pair from an export root, if present."""
    normalised_path = export_root / "normalised" / "normalised_schema.json"
    findings_path = export_root / "normalised" / "audit_findings.json"
    if not normalised_path.exists() or not findings_path.exists():
        return None, None
    model = NormalisedAccount.model_validate(json.loads(normalised_path.read_text(encoding="utf-8")))
    findings = AuditResult.model_validate(json.loads(findings_path.read_text(encoding="utf-8")))
    return model, findings


def _sev_rank(severity: str) -> int:
    return SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else len(SEVERITY_ORDER)


def _sev_label(severity: str) -> str:
    return f"{SEVERITY_ICON.get(severity, '')} {severity}".strip()


def render(model: NormalisedAccount, findings: AuditResult, export_root: Path) -> None:
    st.title("Structural Audit")
    st.caption(f"Export root: `{export_root}`")

    sev_counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings.findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    cols = st.columns(2 + len(SEVERITY_ORDER))
    cols[0].metric("Boards audited", len(model.boards))
    cols[1].metric("Findings", len(findings.findings))
    for i, sev in enumerate(SEVERITY_ORDER):
        cols[2 + i].metric(sev.capitalize(), sev_counts[sev])

    st.divider()
    st.subheader("Rules fired")

    rule_stats: dict[str, dict] = {}
    for f in findings.findings:
        entry = rule_stats.setdefault(f.rule_id, {"count": 0, "severity": f.severity})
        entry["count"] += 1
    rule_rows = [
        {"Rule": rule_id, "Severity": _sev_label(data["severity"]), "Occurrences": data["count"]}
        for rule_id, data in sorted(rule_stats.items(), key=lambda kv: _sev_rank(kv[1]["severity"]))
    ]
    st.dataframe(rule_rows, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Boards")
    severity_filter = st.multiselect("Filter by severity", SEVERITY_ORDER, default=SEVERITY_ORDER)

    by_board: dict[str, list[AuditFinding]] = {}
    for f in findings.findings:
        by_board.setdefault(f.object_id, []).append(f)

    for board in model.boards:
        board_findings = [f for f in by_board.get(board.id, []) if f.severity in severity_filter]
        with st.expander(f"{board.name}  ·  {board.id}  ·  {len(board_findings)} findings"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Groups", len(board.groups))
            c2.metric("Columns", len(board.columns))
            c3.metric("Sample items", board.item_count if board.item_count is not None else "n/a")
            if board.automations:
                cross_board = sum(1 for a in board.automations if a.is_cross_board)
                st.caption(f"{len(board.automations)} automation(s) · {cross_board} cross-board")
            if not board_findings:
                st.info("No findings at the selected severity levels.")
                continue
            rows = [
                {
                    "Severity": _sev_label(f.severity),
                    "Rule": f.rule_id,
                    "Finding": f.finding,
                    "Recommendation": f.recommendation,
                }
                for f in sorted(board_findings, key=lambda f: _sev_rank(f.severity))
            ]
            st.dataframe(rows, width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="MondayMaster — Structural Audit", layout="wide")
    st.sidebar.title("MondayMaster")
    default_root = "exports" if Path("exports/normalised/normalised_schema.json").exists() else "exports_demo"
    export_root = Path(st.sidebar.text_input("Export root", value=default_root))

    model, findings = load_run(export_root)
    if model is None:
        st.warning(
            f"No normalised/audit artefacts found under `{export_root}`.\n\n"
            "Run `python -m app.cli export-all`, `normalise`, and `audit` first "
            "(or `python scripts/demo_hacksaw_run.py` for a demo run without a monday.com token)."
        )
        return
    render(model, findings, export_root)


if __name__ == "__main__":
    main()
