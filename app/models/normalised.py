from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.monday_raw import AutomationActionType, AutomationTriggerType


class NormalisedGroup(BaseModel):
    id: str
    title: str
    item_count: int = 0


class NormalisedColumn(BaseModel):
    id: str
    title: str
    type: str
    normalised_type: str
    settings: dict = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    relationship_targets: list[str] = Field(default_factory=list)
    is_locked: bool = False


class NormalisedWorkspace(BaseModel):
    id: str
    name: str
    board_ids: list[str] = Field(default_factory=list)


class NormalisedAutomation(BaseModel):
    board_id: str
    board_name: str
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    target_board_id: str | None = None
    target_board_name: str | None = None
    is_cross_board: bool = False


class NormalisedBoard(BaseModel):
    id: str
    name: str
    workspace_id: str | None = None
    purpose_guess: str | None = None
    groups: list[NormalisedGroup] = Field(default_factory=list)
    columns: list[NormalisedColumn] = Field(default_factory=list)
    item_count: int | None = None
    risks: list[str] = Field(default_factory=list)
    automations: list[NormalisedAutomation] = Field(default_factory=list)


class NormalisedAccount(BaseModel):
    account: dict = Field(default_factory=dict)
    users: list[dict] = Field(default_factory=list)
    workspaces: list[NormalisedWorkspace] = Field(default_factory=list)
    boards: list[NormalisedBoard] = Field(default_factory=list)
