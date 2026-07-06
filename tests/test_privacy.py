from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.exporters.monday_exporter import MondayExporter
from app.audits.engine import AuditEngine
from app.clients.monday_client import MondayClient
from app.normalisers.monday_normaliser import MondayNormaliser
from app.privacy.outbound import validate_outbound_payload
from app.privacy.policy import PrivacyViolation, TechnicalDataSanitiser, scan_export_tree, validate_artefact
from app.reports.markdown_reporter import MarkdownReporter
from app.storage.artefact_store import ArtefactStore


class FakeMondayClient:
    def __init__(self):
        self.users_called = False

    def get_account(self):
        return {"id": "100", "name": "Secret Company", "slug": "secret-company"}

    def get_users(self):
        self.users_called = True
        return [{"id": "7", "name": "Jane Doe", "email": "jane@example.com"}]

    def get_workspaces(self):
        return [{"id": "200", "name": "Acquisition", "description": "Internal", "kind": "open", "state": "active"}]

    def get_boards(self):
        return [{"id": "300", "name": "Jane's cases", "description": "Internal", "state": "active", "board_kind": "public", "workspace_id": "200"}]

    def get_board_schema(self, board_id):
        return {
            "id": board_id,
            "name": "Jane's cases",
            "description": "Internal",
            "workspace_id": "200",
            "state": "active",
            "board_kind": "public",
            "groups": [{"id": "400", "title": "Customer names"}],
            "columns": [
                {"id": "500", "title": "Email", "type": "text", "settings_str": '{"labels":{"1":"Secret"}}'}
            ],
        }

    def get_all_board_items(self, board_id, limit=None):
        return [{"id": "600", "name": "Jane Doe", "column_values": [{"text": "jane@example.com"}]}]


class PrivacyTests(unittest.TestCase):
    def test_validator_rejects_identity_and_content(self):
        with self.assertRaises(PrivacyViolation):
            validate_artefact({"users": [{"name": "Jane Doe", "email": "jane@example.com"}]})
        with self.assertRaises(PrivacyViolation):
            validate_artefact({"id": "raw-monday-id"})
        with self.assertRaises(PrivacyViolation):
            validate_artefact({"column_values": [{"text": "secret"}]})

    def test_export_all_persists_only_technical_metadata(self):
        client = FakeMondayClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtefactStore(temp_dir)
            run = MondayExporter(client, store).export_all(sample_items=10)
            all_text = "\n".join(
                path.read_text(encoding="utf-8") for path in run.rglob("*.json")
            )
            for sensitive in ("Secret Company", "Acquisition", "Jane", "jane@example.com", "Customer names"):
                self.assertNotIn(sensitive, all_text)
            self.assertFalse(client.users_called)
            self.assertEqual(json.loads((run / "users.json").read_text()), [])
            sample_path = next((run / "boards").glob("*_items_sample.json"))
            sample = json.loads(sample_path.read_text())
            self.assertEqual(sample["sample_count"], 1)
            self.assertFalse(sample["content_exported"])
            for path in run.rglob("*.json"):
                validate_artefact(json.loads(path.read_text(encoding="utf-8")))

    def test_sanitiser_references_are_run_scoped_and_consistent(self):
        first = TechnicalDataSanitiser(b"a" * 32)
        second = TechnicalDataSanitiser(b"b" * 32)
        self.assertEqual(first.ref("board", "123"), first.ref("board", "123"))
        self.assertNotEqual(first.ref("board", "123"), second.ref("board", "123"))

    def test_outbound_payload_rejects_extra_fields(self):
        payload = {
            "schema_version": "1.0",
            "privacy_mode": "technical_metadata_only",
            "account_metrics": {"workspace_count": 0, "board_count": 0},
            "boards": [],
        }
        validate_outbound_payload(payload)
        payload["company_name"] = "Secret Company"
        with self.assertRaises(ValueError):
            validate_outbound_payload(payload)

    def test_monday_queries_request_no_identity_or_content_fields(self):
        client = object.__new__(MondayClient)
        queries = []

        def capture(query, variables=None):
            queries.append(query)
            return {}

        client.query = capture
        client.test_connection()
        client.get_account()
        client.get_workspaces()
        client.get_users()
        client.get_boards()
        client.get_boards("workspace-id")
        client.get_board_schema("board-id")
        client.get_board_items_page("board-id")
        client.get_board_items_page("board-id", cursor="cursor")

        query_text = "\n".join(queries).lower()
        for forbidden_field in (
            " name",
            "email",
            "description",
            "column_values",
            "subitems",
            "settings_str",
            "updates",
            "files",
        ):
            self.assertNotIn(forbidden_field, query_text)

    def test_complete_local_pipeline_remains_privacy_safe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtefactStore(temp_dir)
            MondayExporter(FakeMondayClient(), store).export_all(sample_items=10)
            MondayNormaliser(store).normalise_latest()
            AuditEngine(store).run()
            report_paths = MarkdownReporter(store).generate()
            self.assertEqual(len(report_paths), 2)
            self.assertEqual(scan_export_tree(Path(temp_dir)), [])


if __name__ == "__main__":
    unittest.main()
