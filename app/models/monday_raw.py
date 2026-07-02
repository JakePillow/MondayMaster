from pydantic import BaseModel, Field


class MondayRawExport(BaseModel):
    run_id: str
    account: dict = Field(default_factory=dict)
    users: list[dict] = Field(default_factory=list)
    workspaces: list[dict] = Field(default_factory=list)
    boards: list[dict] = Field(default_factory=list)
