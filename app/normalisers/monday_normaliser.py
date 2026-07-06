from __future__ import annotations

import json
from pathlib import Path

from app.models.monday_raw import AutomationActionType, AutomationTriggerType
from app.models.normalised import (
    NormalisedAccount,
    NormalisedAutomation,
    NormalisedBoard,
    NormalisedColumn,
    NormalisedGroup,
    NormalisedWorkspace,
)
from app.storage.artefact_store import ArtefactStore

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


def _build_automation(raw: dict, board_id: str, board_name: str, board_names: dict[str, str]) -> NormalisedAutomation:
    target_board_id = raw.get("target_board_id")
    target_board_id = str(target_board_id) if target_board_id else None
    return NormalisedAutomation(
        board_id=board_id,
        board_name=board_name,
        trigger_type=AutomationTriggerType(raw.get("trigger_type") or AutomationTriggerType.UNKNOWN),
        action_type=AutomationActionType(raw.get("action_type") or AutomationActionType.UNKNOWN),
        target_board_id=target_board_id,
        target_board_name=board_names.get(target_board_id) if target_board_id else None,
        is_cross_board=bool(target_board_id) and target_board_id != board_id,
    )


def build_normalised_board(schema: dict, board_names: dict[str, str], item_count: int | None = None) -> NormalisedBoard:
    board_id = str(schema.get("id"))
    board_name = str(schema.get("name", ""))
    cols = []
    for col in schema.get("columns", []):
        ctype = str(col.get("type", "unknown"))
        cols.append(NormalisedColumn(id=str(col.get("id")), title=str(col.get("title", "")), type=ctype, normalised_type=TYPE_MAP.get(ctype, "unknown"), settings={}, labels=[], relationship_targets=[], is_locked=bool(col.get("locked", False))))
    groups = [NormalisedGroup(id=str(g.get("id")), title=str(g.get("title", "")), item_count=int(g.get("item_count") or 0)) for g in schema.get("groups", [])]
    automations = [_build_automation(a, board_id, board_name, board_names) for a in schema.get("automations", [])]
    return NormalisedBoard(id=board_id, name=board_name, workspace_id=str(schema.get("workspace_id")) if schema.get("workspace_id") else None, groups=groups, columns=cols, item_count=item_count, automations=automations)


class MondayNormaliser:
    def __init__(self, store: ArtefactStore):
        self.store = store

    def normalise_latest(self) -> Path:
        run_dir = self.store.latest_raw_run()
        boards_index = self.store.read_json(run_dir / "boards_index.json") if (run_dir / "boards_index.json").exists() else []
        workspaces_raw = self.store.read_json(run_dir / "workspaces.json") if (run_dir / "workspaces.json").exists() else []
        account = self.store.read_json(run_dir / "account.json") if (run_dir / "account.json").exists() else {}
        users = self.store.read_json(run_dir / "users.json") if (run_dir / "users.json").exists() else []
        schemas = [self.store.read_json(p) for p in sorted((run_dir / "boards").glob("board_*_schema.json"))]
        board_names = {str(s.get("id")): str(s.get("name", "")) for s in schemas}
        boards = []
        for schema in schemas:
            board_id = str(schema.get("id"))
            sample_path = run_dir / "boards" / f"{board_id}_items_sample.json"
            sample = self.store.read_json(sample_path) if sample_path.exists() else None
            item_count = sample.get("sample_count") if isinstance(sample, dict) else None
            boards.append(build_normalised_board(schema, board_names, item_count=item_count))
        workspace_models = []
        for ws in workspaces_raw:
            wid = str(ws.get("id"))
            workspace_models.append(NormalisedWorkspace(id=wid, name=str(ws.get("name", "")), board_ids=[str(b.get("id")) for b in boards_index if str(b.get("workspace_id")) == wid]))
        normalised = NormalisedAccount(account=account, users=users, workspaces=workspace_models, boards=boards)
        path = self.store.normalised_root / "normalised_schema.json"
        self.store.write_json(path, normalised.model_dump())
        return path
