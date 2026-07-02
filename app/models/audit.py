from typing import Literal
from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
ObjectType = Literal["workspace", "board", "column", "automation", "integration"]


class AuditFinding(BaseModel):
    rule_id: str
    severity: Severity
    object_type: ObjectType
    object_id: str
    object_name: str
    finding: str
    evidence: dict = Field(default_factory=dict)
    recommendation: str


class AuditResult(BaseModel):
    findings: list[AuditFinding] = Field(default_factory=list)
