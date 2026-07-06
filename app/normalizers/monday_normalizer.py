from __future__ import annotations

import json
from pathlib import Path

from app.models.normalized import NormalizedAccount, NormalizedBoard, NormalizedColumn, NormalizedGroup, NormalizedWorkspace
from app.storage.artifact_store import ArtifactStore

TYPE_MAP = {
    "status": "status", "dropdown": "dropdown", "people": "people", "person": "people", "date": "date",
    "timeline": "timeline", "formula": "formula", "mirror": "mirror", "board_relation": "connect_board",
    "connect_boards": "connect_board", "dependency": "dependency", "file": "file", "text": "text",
    "long_text": "text", "numbers": "number", "numeric": "number", "link": "link", "name": "text",
}


def _settings(raw: dict) -> dict:
    try:
        return json.loads(raw.get("settings_str") or "{}")
    except json.JSONDecodeError:
        return {}


def _labels(settings: dict) -> list[str]:
    labels = settings.get("labels") or settings.get("labels_colors") or {}
    if isinstance(labels, dict):
        return [str(v.get("label") if isinstance(v, dict) else v) for v in labels.values() if v]
    if isinstance(labels, list):
        return [str(v) for v in labels]
    return []


def _relationship_targets(settings: dict) -> list[str]:
    for key in ("boardIds", "board_ids", "boards"):
        values = settings.get(key)
        if isinstance(values, list):
            return [str(v) for v in values]
    return []


class MondayNormalizer:
    def __init__(self, store: ArtifactStore):
        self.store = store

    def normalize_latest(self) -> Path:
        run_dir = self.store.latest_raw_run()
        boards_index = self.store.read_json(run_dir / "boards_index.json") if (run_dir / "boards_index.json").exists() else []
        workspaces_raw = self.store.read_json(run_dir / "workspaces.json") if (run_dir / "workspaces.json").exists() else []
        account = self.store.read_json(run_dir / "account.json") if (run_dir / "account.json").exists() else {}
        users = self.store.read_json(run_dir / "users.json") if (run_dir / "users.json").exists() else []
        boards = []
        for schema_path in sorted((run_dir / "boards").glob("board_*_schema.json")):
            schema = self.store.read_json(schema_path)
            board_id = str(schema.get("id"))
            sample_path = run_dir / "boards" / f"{board_id}_items_sample.json"
            sample = self.store.read_json(sample_path) if sample_path.exists() else None
            item_count = sample.get("sample_count") if isinstance(sample, dict) else None
            cols = []
            for col in schema.get("columns", []):
                ctype = str(col.get("type", "unknown"))
                cols.append(NormalizedColumn(id=str(col.get("id")), title=str(col.get("title", "")), type=ctype, normalized_type=TYPE_MAP.get(ctype, "unknown"), settings={}, labels=[], relationship_targets=[]))
            boards.append(NormalizedBoard(id=board_id, name=str(schema.get("name", "")), workspace_id=str(schema.get("workspace_id")) if schema.get("workspace_id") else None, groups=[NormalizedGroup(id=str(g.get("id")), title=str(g.get("title", ""))) for g in schema.get("groups", [])], columns=cols, item_count=item_count))
        workspace_models = []
        for ws in workspaces_raw:
            wid = str(ws.get("id"))
            workspace_models.append(NormalizedWorkspace(id=wid, name=str(ws.get("name", "")), board_ids=[str(b.get("id")) for b in boards_index if str(b.get("workspace_id")) == wid]))
        normalized = NormalizedAccount(account=account, users=users, workspaces=workspace_models, boards=boards)
        path = self.store.normalized_root / "normalized_schema.json"
        self.store.write_json(path, normalized.model_dump())
        return path
