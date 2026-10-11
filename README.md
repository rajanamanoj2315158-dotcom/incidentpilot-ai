# IncidentPilot AI

An evidence-led incident response service: detect, collect evidence, investigate with Sarvam AI, diagnose with explicit uncertainty, require human approval, and produce reports. It intentionally refuses production execution.

## Architecture

The React/Vite dashboard reads the FastAPI `/api/v1` service. The service stores normalized incidents and audit events in SQLite for local development; its provider boundary supports Sarvam plus deterministic test runs. The agent only selects from a fixed evidence-tool registry—there is no shell, SQL, or arbitrary URL tool.

Sarvam uses the documented stable `POST https://api.sarvam.ai/v1/chat/completions` endpoint and `api-subscription-key` header with `sarvam-105b` by default. It is never exposed to the browser. Native external adapters are intentionally reported as unconfigured until connection settings and credentials are supplied.

## Run locally

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

In a second terminal:

```sh
cd frontend
npm install
npm run dev
```

Add a *newly generated* key only to `incidentpilot-ai/.env` as `SARVAM_API_KEY=...`; do not commit it. The OpenAPI console is at `http://localhost:8000/docs`.

## Synthetic demonstration

Create an incident with `POST /api/v1/incidents`, then use `POST /api/v1/incidents/{id}/investigate?test_provider=true`. This explicitly selects the deterministic, offline test provider—no live AI call is implied. The result labels evidence as synthetic and reports limited confidence.

## Authorization and remediation

Sensitive endpoints require `X-Role: operator` (or `admin`) and, when `OPERATOR_TOKEN` is configured, `X-Operator-Token`. Approvals bind to an incident, action, target and environment, expire, and cannot be replayed. Production operations are hard-disabled. The only initial rollback execution response is a clearly labelled staging/local simulation; it makes no recovery claim.

## Tests and deployment

Run `cd backend && pytest -q`. Docker: `cp .env.example .env && docker compose up --build`. For deployment, use PostgreSQL and add a migration layer before production, configure a real authentication provider, webhook signature secret, Prometheus/OTel adapters, and a least-privilege GitHub integration. Never enable production execution without a reviewed policy and independent health verification.
