"""Run the real export -> normalise -> audit -> report pipeline against a stand-in
client shaped like the Hacksaw "Access & Grant Management" case study (docs/PROJECT_CONTEXT.md
section 6). There is no live MONDAY_API_TOKEN configured, so this exercises the actual
pipeline code end-to-end without touching a real monday.com account.

Usage: python scripts/demo_hacksaw_run.py [export_root]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audits.engine import AuditEngine
from app.exporters.monday_exporter import MondayExporter
from app.normalisers.monday_normaliser import MondayNormaliser
from app.reports.markdown_reporter import MarkdownReporter
from app.storage.artefact_store import ArtefactStore


class DemoMondayClient:
    def get_account(self):
        return {"id": "9001", "name": "Hacksaw Gaming"}

    def get_workspaces(self):
        return [{"id": "web-ws-1", "name": "Hacksaw Gaming", "kind": "open", "state": "active"}]

    def get_users(self):
        return []

    def get_boards(self, workspace_id=None):
        return [
            {"id": "tmpl-001", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1"},
            {"id": "prog-002", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1"},
            {"id": "comp-003", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1"},
        ]

    def get_board_schema(self, board_id: str) -> dict:
        boards = {
            "tmpl-001": {
                "id": "tmpl-001", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1",
                "columns": [
                    {"id": "team", "type": "text", "locked": True},
                    {"id": "spec", "type": "long_text", "locked": True},
                ],
                "groups": [{"id": "g1", "items_count": 15}],
                "automations": [
                    {"trigger_type": "button_click", "action_type": "create_item", "target_board_id": "prog-002"},
                ],
            },
            "prog-002": {
                "id": "prog-002", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1",
                "columns": [
                    {"id": "approver", "type": "person", "locked": True},
                    {"id": "tool_admin", "type": "person", "locked": True},
                    {"id": "status", "type": "status", "locked": True},
                    {"id": "resolution", "type": "status", "locked": True},
                    {"id": "personnel_group", "type": "text", "locked": True},
                ],
                "groups": [{"id": "all", "items_count": 56}],
                "automations": [],
            },
            "comp-003": {
                "id": "comp-003", "state": "active", "board_kind": "public", "workspace_id": "web-ws-1",
                "columns": [{"id": "approver2", "type": "person", "locked": True}],
                "groups": [{"id": "all2", "items_count": 3798}],
                "automations": [],
            },
        }
        return boards[board_id]

    def get_all_board_items(self, board_id: str, limit=None):
        counts = {"tmpl-001": 15, "prog-002": 56, "comp-003": 3798}
        n = min(counts[board_id], limit or counts[board_id])
        return [{"id": str(i)} for i in range(n)]


def main() -> None:
    export_root = sys.argv[1] if len(sys.argv) > 1 else "exports_demo"
    store = ArtefactStore(export_root)
    client = DemoMondayClient()

    run_dir = MondayExporter(client, store).export_all(sample_items=100)
    print(f"Exported to {run_dir}")

    normalised_path = MondayNormaliser(store).normalise_latest()
    print(f"Normalised to {normalised_path}")

    audit_path = AuditEngine(store).run()
    print(f"Audit findings at {audit_path}")

    report_paths = MarkdownReporter(store).generate()
    for path in report_paths:
        print(f"Report written to {path}")


if __name__ == "__main__":
    main()
