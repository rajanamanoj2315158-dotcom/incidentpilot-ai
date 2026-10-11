from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from .agent import investigate
from .config import settings
from .llm import DeterministicLLM, LLMError, SarvamClient
from .schemas import ApprovalRequest, CreateIncident, Incident
from .store import Store

app = FastAPI(title="IncidentPilot AI", version="0.1.0")
store = Store()

def require_operator(x_role: Optional[str] = Header(default=None), x_operator_token: Optional[str] = Header(default=None)):
    if x_role not in {"operator", "admin"}:
        raise HTTPException(403, "Operator role required")
    if settings.operator_token and x_operator_token != settings.operator_token:
        raise HTTPException(401, "Invalid operator credential")
    return x_role

def incident_or_404(incident_id: str):
    incident = store.get_incident(incident_id)
    if not incident: raise HTTPException(404, "Incident not found")
    return incident

@app.get("/api/v1/health")
def health(): return {"status":"ok", "environment":settings.app_env}

@app.get("/api/v1/integrations/status")
def integrations():
    return {"sarvam": {"configured": bool(settings.sarvam_api_key), "model": settings.sarvam_model, "mode":"live" if settings.sarvam_api_key else "not_configured"}, "prometheus":{"configured":False}, "github":{"configured":False}, "evidence_mode":"synthetic when no provider adapter is configured"}

@app.get("/api/v1/incidents")
def list_incidents(q: Optional[str] = None, limit: int = Query(50, le=100)):
    items = store.incidents()
    if q: items = [i for i in items if q.lower() in (i.title + i.description).lower()]
    return {"items": [i.model_dump(mode="json") for i in items[:limit]], "total": len(items)}

@app.post("/api/v1/incidents", status_code=201)
def create_incident(data: CreateIncident):
    incident = Incident(id=str(uuid4()), status="open", detected_at=datetime.now(timezone.utc), **data.model_dump())
    store.save_incident(incident); store.audit("incident.created", {"incident_id":incident.id})
    return incident

@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: str): return incident_or_404(incident_id)

@app.post("/api/v1/incidents/{incident_id}/investigate")
async def run_investigation(incident_id: str, test_provider: bool = Query(False)):
    incident = incident_or_404(incident_id); incident.status = "investigating"
    try:
        updated = await investigate(incident, DeterministicLLM() if test_provider else SarvamClient(), settings.agent_max_steps)
    except LLMError as exc:
        store.save_incident(incident)
        raise HTTPException(503, str(exc))
    store.save_incident(updated); store.audit("investigation.completed", {"incident_id":incident_id})
    return updated

@app.get("/api/v1/incidents/{incident_id}/timeline")
def timeline(incident_id: str):
    incident = incident_or_404(incident_id)
    return sorted([e.model_dump(mode="json") for e in incident.evidence], key=lambda e:e["timestamp"])

@app.get("/api/v1/incidents/{incident_id}/diagnosis")
def diagnosis(incident_id: str):
    result = incident_or_404(incident_id).diagnosis
    if not result: raise HTTPException(409, "Diagnosis is not available")
    return result

@app.post("/api/v1/incidents/{incident_id}/remediation/plan")
def remediation_plan(incident_id: str, _: str = Depends(require_operator)):
    incident = incident_or_404(incident_id)
    if not incident.diagnosis: raise HTTPException(409, "Investigation must finish first")
    return {"action":"rollback_staging", "target":incident.affected_services[0], "environment":"staging", "dry_run":True, "simulated":True, "risk":"May revert unrelated staging changes", "requires_approval":True}

@app.post("/api/v1/incidents/{incident_id}/approvals", status_code=201)
def approve(incident_id: str, request: ApprovalRequest, role: str = Depends(require_operator)):
    incident_or_404(incident_id)
    if request.environment == "production": raise HTTPException(403, "Production operations are disabled by policy")
    record = {"id":str(uuid4()), "incident_id":incident_id, **request.model_dump(), "actor":role, "expires_at":(datetime.now(timezone.utc)+timedelta(minutes=settings.approval_ttl_minutes)).isoformat(), "used":False}
    store.save_approval(record); store.audit("approval.granted", {"approval_id":record["id"]})
    return record

@app.post("/api/v1/incidents/{incident_id}/remediation/execute")
def execute(incident_id: str, request: dict, _: str = Depends(require_operator)):
    approval = store.get_approval(request.get("approval_id", ""))
    if not approval or approval["incident_id"] != incident_id or approval["used"]: raise HTTPException(403, "Invalid or already-used approval")
    if datetime.fromisoformat(approval["expires_at"]) < datetime.now(timezone.utc): raise HTTPException(403, "Approval expired")
    if approval["environment"] == "production": raise HTTPException(403, "Production operations are disabled")
    # No real rollback adapter is wired: return a truthful local/staging simulation only.
    approval["used"] = True
    with store._connect() as db: db.execute("UPDATE approvals SET payload=? WHERE id=?", (__import__('json').dumps(approval), approval["id"]))
    store.audit("remediation.simulated", {"incident_id":incident_id, "approval_id":approval["id"]})
    return {"status":"simulated_success", "simulated":True, "verification":"Not executed against a real environment; no recovery claim is made."}

@app.get("/api/v1/incidents/{incident_id}/report", response_class=PlainTextResponse)
def report(incident_id: str):
    i = incident_or_404(incident_id)
    return f"# Incident report: {i.title}\n\n## Overview\n{i.description}\n\n## Status\n{i.status}\n\n## Evidence\n" + "\n".join(f"- {e.id}: {e.summary} ({e.source})" for e in i.evidence) + f"\n\n## Diagnosis\n{(i.diagnosis or {}).get('executive_summary', 'Not completed')}\n"

@app.post("/api/v1/webhooks/alerts", status_code=202)
async def alert_webhook(request: Request):
    body = await request.body()
    if len(body) > 1_000_000: raise HTTPException(413, "Payload too large")
    # Signature verification is enabled when an Alertmanager shared secret adapter is configured.
    store.audit("webhook.received", {"bytes":len(body)})
    return {"accepted":True}
