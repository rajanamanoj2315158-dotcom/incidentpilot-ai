from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class IncidentStatus(StrEnum):
    open = "open"
    investigating = "investigating"
    diagnosed = "diagnosed"
    mitigated = "mitigated"


class Evidence(BaseModel):
    id: str
    kind: str
    timestamp: datetime
    service: str
    summary: str
    data: dict = Field(default_factory=dict)
    source: str = "synthetic"


class CreateIncident(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    severity: Severity
    affected_services: list[str] = Field(min_length=1, max_length=20)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)


class Incident(BaseModel):
    id: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    detected_at: datetime
    affected_services: list[str]
    evidence: list[Evidence]
    investigation_steps: list[dict] = Field(default_factory=list)
    diagnosis: dict | None = None


class ApprovalRequest(BaseModel):
    action: str = Field(pattern="^(prepare_patch|create_github_pr|rollback_staging)$")
    target: str = Field(min_length=1, max_length=300)
    environment: str = Field(pattern="^(local|staging|production)$")


class ExecuteRequest(BaseModel):
    approval_id: str

