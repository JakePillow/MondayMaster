from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AutomationTriggerType(str, Enum):
    BUTTON_CLICK = "button_click"
    STATUS_CHANGE = "status_change"
    ITEM_CREATED = "item_created"
    DATE_ARRIVES = "date_arrives"
    COLUMN_CHANGE = "column_change"
    UNKNOWN = "unknown"


class AutomationActionType(str, Enum):
    CREATE_ITEM = "create_item"
    NOTIFY = "notify"
    MOVE_ITEM = "move_item"
    CHANGE_COLUMN = "change_column"
    UNKNOWN = "unknown"


class RawAutomation(BaseModel):
    """Enough to detect a cross-board trigger (rule: cross_board_automation_trigger) — not a full recipe.

    `raw_description` is a scrape-path convenience for manually classifying trigger/action type
    from a recipe's plain-language text (e.g. "Create AGM Ticket"). It is intentionally dropped
    by the normaliser and must never be written to a stored artefact — PRIVACY.md forbids
    persisting free text of any kind.
    """

    automation_id: str | None = None
    board_id: str
    trigger_type: AutomationTriggerType = AutomationTriggerType.UNKNOWN
    action_type: AutomationActionType = AutomationActionType.UNKNOWN
    target_board_id: str | None = None
    raw_description: str | None = None


class RawColumn(BaseModel):
    id: str
    title: str = ""
    type: str = "unknown"
    locked: bool = False


class RawGroup(BaseModel):
    id: str
    title: str = ""
    item_count: int = 0


class RawBoard(BaseModel):
    id: str
    name: str = ""
    workspace_id: str | None = None
    groups: list[RawGroup] = Field(default_factory=list)
    columns: list[RawColumn] = Field(default_factory=list)
    automations: list[RawAutomation] = Field(default_factory=list)


class MondayRawExport(BaseModel):
    run_id: str
    account: dict = Field(default_factory=dict)
    users: list[dict] = Field(default_factory=list)
    workspaces: list[dict] = Field(default_factory=list)
    boards: list[dict] = Field(default_factory=list)
