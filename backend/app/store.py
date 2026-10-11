from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Optional
from .schemas import Incident


class Store:
    def __init__(self, path: str = "incidentpilot.db"):
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, incident_id TEXT, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, payload TEXT)")

    def save_incident(self, incident: Incident):
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO incidents VALUES (?,?)", (incident.id, incident.model_dump_json()))

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def incidents(self) -> list[Incident]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM incidents").fetchall()
        return [Incident.model_validate_json(row[0]) for row in rows]

    def save_approval(self, approval: dict):
        with self._connect() as db:
            db.execute("INSERT INTO approvals VALUES (?,?,?)", (approval["id"], approval["incident_id"], json.dumps(approval, default=str)))

    def get_approval(self, approval_id: str) -> Optional[dict]:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def audit(self, event: str, payload: dict):
        with self._connect() as db:
            db.execute("INSERT INTO audit(event,payload) VALUES (?,?)", (event, json.dumps(payload, default=str)))
