from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.monday_raw import AutomationActionType, AutomationTriggerType


class NormalizedGroup(BaseModel):
    id: str
    title: str
    item_count: int = 0


class NormalizedColumn(BaseModel):
    id: str
    title: str
    type: str
    normalized_type: str
    settings: dict = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    relationship_targets: list[str] = Field(default_factory=list)
    is_locked: bool = False


class NormalizedWorkspace(BaseModel):
    id: str
    name: str
    board_ids: list[str] = Field(default_factory=list)


class NormalizedAutomation(BaseModel):
    board_id: str
    board_name: str
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    target_board_id: str | None = None
    target_board_name: str | None = None
    is_cross_board: bool = False


class NormalizedBoard(BaseModel):
    id: str
    name: str
    workspace_id: str | None = None
    purpose_guess: str | None = None
    groups: list[NormalizedGroup] = Field(default_factory=list)
    columns: list[NormalizedColumn] = Field(default_factory=list)
    item_count: int | None = None
    risks: list[str] = Field(default_factory=list)
    automations: list[NormalizedAutomation] = Field(default_factory=list)


class NormalizedAccount(BaseModel):
    account: dict = Field(default_factory=dict)
    users: list[dict] = Field(default_factory=list)
    workspaces: list[NormalizedWorkspace] = Field(default_factory=list)
    boards: list[NormalizedBoard] = Field(default_factory=list)
