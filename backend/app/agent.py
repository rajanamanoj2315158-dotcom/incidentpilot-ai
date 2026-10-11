from .schemas import Incident, Evidence
from .llm import LLM, AgentDecision

TOOLS = {"alerts", "logs", "traces", "deployments"}


def correlate(incident: Incident) -> dict:
    deployments = [e for e in incident.evidence if e.kind == "deployment"]
    errors = [e for e in incident.evidence if e.kind in {"alert", "log", "trace"}]
    return {"deployment_near_incident": bool(deployments and errors), "evidence_ids": [e.id for e in incident.evidence]}


async def investigate(incident: Incident, llm: LLM, max_steps: int) -> Incident:
    prompt = f"Incident: {incident.title}\nEvidence: {[e.model_dump(mode='json') for e in incident.evidence]}"
    for number in range(max_steps):
        decision = await llm.decide(prompt)
        if decision.action == "investigate" and decision.tool in TOOLS:
            incident.investigation_steps.append({"step": number + 1, "tool": decision.tool, "rationale": decision.rationale, "result": "No external provider connected; assessed normalized evidence only."})
            prompt += f"\nTool {decision.tool} completed using available incident evidence."
            continue
        if decision.action == "diagnose":
            facts = correlate(incident)
            incident.diagnosis = {"executive_summary": decision.hypothesis or "Investigation inconclusive.", "confidence": "limited", "confidence_note": "Correlation does not prove causation; validate with rollback or comparison.", "supporting_evidence": facts["evidence_ids"], "contradicting_evidence": [], "missing_evidence": ["pre-deployment baseline metrics"], "recommended_remediation": "Prepare a patch or staging rollback plan; human approval is required.", "verification_plan": "Confirm error rate and p95 latency return to baseline."}
            incident.status = "diagnosed"
            return incident
        break
    incident.investigation_steps.append({"step": max_steps, "tool": None, "rationale": "Investigation step limit reached.", "result": "Stopped safely."})
    return incident
