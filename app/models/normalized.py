from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedGroup(BaseModel):
    id: str
    title: str


class NormalizedColumn(BaseModel):
    id: str
    title: str
    type: str
    normalized_type: str
    settings: dict = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    relationship_targets: list[str] = Field(default_factory=list)


class NormalizedWorkspace(BaseModel):
    id: str
    name: str
    board_ids: list[str] = Field(default_factory=list)


class NormalizedBoard(BaseModel):
    id: str
    name: str
    workspace_id: str | None = None
    purpose_guess: str | None = None
    groups: list[NormalizedGroup] = Field(default_factory=list)
    columns: list[NormalizedColumn] = Field(default_factory=list)
    item_count: int | None = None
    risks: list[str] = Field(default_factory=list)


class NormalizedAccount(BaseModel):
    account: dict = Field(default_factory=dict)
    users: list[dict] = Field(default_factory=list)
    workspaces: list[NormalizedWorkspace] = Field(default_factory=list)
    boards: list[NormalizedBoard] = Field(default_factory=list)
