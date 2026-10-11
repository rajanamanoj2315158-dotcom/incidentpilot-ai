from fastapi.testclient import TestClient
from app.main import app, store

client = TestClient(app)

def make_incident():
    r = client.post('/api/v1/incidents', json={"title":"Checkout failures","description":"Elevated 500s after deploy","severity":"high","affected_services":["checkout"],"evidence":[{"id":"a1","kind":"alert","timestamp":"2026-01-01T10:00:00Z","service":"checkout","summary":"5xx rate elevated"},{"id":"d1","kind":"deployment","timestamp":"2026-01-01T09:58:00Z","service":"checkout","summary":"v2 deployed"}]})
    assert r.status_code == 201; return r.json()['id']

def test_investigate_with_deterministic_provider():
    incident_id = make_incident()
    r = client.post(f'/api/v1/incidents/{incident_id}/investigate?test_provider=true')
    assert r.status_code == 200 and r.json()['diagnosis']['confidence'] == 'limited'

def test_production_approval_is_blocked():
    incident_id = make_incident()
    r = client.post(f'/api/v1/incidents/{incident_id}/approvals', headers={'X-Role':'operator'}, json={'action':'rollback_staging','target':'checkout','environment':'production'})
    assert r.status_code == 403

def test_report_is_generated():
    incident_id = make_incident()
    assert client.get(f'/api/v1/incidents/{incident_id}/report').status_code == 200
