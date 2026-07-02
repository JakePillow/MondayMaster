from pydantic import BaseModel, Field


class GeneratedReport(BaseModel):
    path: str
    title: str
    sections: list[str] = Field(default_factory=list)
