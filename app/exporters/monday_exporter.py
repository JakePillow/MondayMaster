from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.privacy.policy import TechnicalDataSanitizer
from app.storage.artifact_store import ArtifactStore

if TYPE_CHECKING:
    from app.clients.monday_client import MondayClient


class MondayExporter:
    def __init__(self, client: MondayClient, store: ArtifactStore):
        self.client = client
        self.store = store
        self.sanitizer = TechnicalDataSanitizer()

    def _start_run(self) -> Path:
        run_dir = self.store.new_run_dir()
        self.store.write_json(run_dir / "privacy_manifest.json", self.sanitizer.manifest())
        return run_dir

    def export_account(self) -> Path:
        run_dir = self._start_run()
        self.store.write_json(run_dir / "account.json", self.sanitizer.account(self.client.get_account()))
        return run_dir

    def export_workspaces(self) -> Path:
        run_dir = self._start_run()
        workspaces = [self.sanitizer.workspace(ws) for ws in self.client.get_workspaces()]
        self.store.write_json(run_dir / "workspaces.json", workspaces)
        return run_dir

    def export_boards(self) -> Path:
        run_dir = self._start_run()
        boards = [self.sanitizer.board_index(board) for board in self.client.get_boards()]
        self.store.write_json(run_dir / "boards_index.json", boards)
        return run_dir

    def export_all(self, sample_items: int = 100) -> Path:
        run_dir = self._start_run()
        self.store.write_json(run_dir / "account.json", self.sanitizer.account(self.client.get_account()))
        # Keep a stable artifact without collecting any user profiles.
        self.store.write_json(run_dir / "users.json", [])
        workspaces = [self.sanitizer.workspace(ws) for ws in self.client.get_workspaces()]
        self.store.write_json(run_dir / "workspaces.json", workspaces)
        raw_boards = self.client.get_boards()
        boards = [self.sanitizer.board_index(board) for board in raw_boards]
        self.store.write_json(run_dir / "boards_index.json", boards)
        for raw_board, board in zip(raw_boards, boards):
            monday_board_id = str(raw_board["id"])
            board_ref = str(board["id"])
            schema = self.sanitizer.board_schema(self.client.get_board_schema(monday_board_id))
            self.store.write_json(run_dir / "boards" / f"{board_ref}_schema.json", schema)
            items = self.client.get_all_board_items(monday_board_id, limit=sample_items)
            summary = self.sanitizer.item_sample_summary(items, sample_items)
            self.store.write_json(run_dir / "boards" / f"{board_ref}_items_sample.json", summary)
        return run_dir

    def export_board(self, board_id: str, sample_items: int = 100) -> Path:
        run_dir = self._start_run()
        schema = self.sanitizer.board_schema(self.client.get_board_schema(board_id))
        board_ref = str(schema["id"])
        self.store.write_json(run_dir / "boards" / f"{board_ref}_schema.json", schema)
        items = self.client.get_all_board_items(board_id, limit=sample_items)
        summary = self.sanitizer.item_sample_summary(items, sample_items)
        self.store.write_json(run_dir / "boards" / f"{board_ref}_items_sample.json", summary)
        return run_dir
