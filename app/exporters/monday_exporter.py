from __future__ import annotations

from pathlib import Path

from app.clients.monday_client import MondayClient
from app.storage.artifact_store import ArtifactStore


class MondayExporter:
    def __init__(self, client: MondayClient, store: ArtifactStore):
        self.client = client
        self.store = store

    def export_all(self, sample_items: int = 100) -> Path:
        run_dir = self.store.new_run_dir()
        self.store.write_json(run_dir / "account.json", self.client.get_account())
        self.store.write_json(run_dir / "users.json", self.client.get_users())
        workspaces = self.client.get_workspaces()
        self.store.write_json(run_dir / "workspaces.json", workspaces)
        boards = self.client.get_boards()
        self.store.write_json(run_dir / "boards_index.json", boards)
        for board in boards:
            board_id = str(board["id"])
            schema = self.client.get_board_schema(board_id)
            self.store.write_json(run_dir / "boards" / f"board_{board_id}_schema.json", schema)
            items = self.client.get_all_board_items(board_id, limit=sample_items)
            self.store.write_json(run_dir / "boards" / f"board_{board_id}_items_sample.json", items)
        return run_dir

    def export_board(self, board_id: str, sample_items: int = 100) -> Path:
        run_dir = self.store.new_run_dir()
        self.store.write_json(run_dir / "boards" / f"board_{board_id}_schema.json", self.client.get_board_schema(board_id))
        self.store.write_json(run_dir / "boards" / f"board_{board_id}_items_sample.json", self.client.get_all_board_items(board_id, limit=sample_items))
        return run_dir
