"""SQLite persistence layer. The database is the source of truth for the local app."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AuditEvent, new_id

DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "mission_validation.db"

TABLES = {
    "projects": "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "vehicles": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "missions": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "artifacts": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "flights": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "telemetry_packets": "id INTEGER PRIMARY KEY AUTOINCREMENT, flight_id TEXT NOT NULL, packet_number INTEGER NOT NULL, timestamp_s REAL NOT NULL, payload TEXT NOT NULL",
    "simulation_runs": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "scenarios": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "test_cases": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "test_runs": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "requirements": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "config_revisions": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "security_findings": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "reports": "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL",
    "audit_events": "id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT, actor TEXT, action TEXT, object_id TEXT, result TEXT, detail TEXT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize() -> None:
    """Create all local tables and indexes idempotently."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as db:
        for table, columns in TABLES.items():
            db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
        db.execute("CREATE INDEX IF NOT EXISTS idx_packets_flight_time ON telemetry_packets(flight_id, timestamp_s)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(occurred_at)")


def _save(table: str, object_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = _now()
    payload = {**payload, "id": object_id, "created_at": payload.get("created_at", timestamp), "updated_at": timestamp}
    with sqlite3.connect(DATABASE_PATH) as db:
        if table == "projects":
            db.execute("INSERT OR REPLACE INTO projects (id, created_at, updated_at, payload) VALUES (?, ?, ?, ?)", (object_id, payload["created_at"], timestamp, json.dumps(payload)))
        else:
            db.execute(f"INSERT OR REPLACE INTO {table} (id, project_id, created_at, updated_at, payload) VALUES (?, ?, ?, ?, ?)", (object_id, project_id, payload["created_at"], timestamp, json.dumps(payload)))
    return payload


def _get(table: str, object_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(DATABASE_PATH) as db:
        row = db.execute(f"SELECT payload FROM {table} WHERE id = ?", (object_id,)).fetchone()
    return json.loads(row[0]) if row else None


def _list(table: str, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with sqlite3.connect(DATABASE_PATH) as db:
        rows = db.execute(f"SELECT payload FROM {table} WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, limit)).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_project(payload: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    return _save("projects", project_id or new_id("project"), project_id or payload.get("id", ""), payload)


def get_project(project_id: str) -> dict[str, Any] | None:
    return _get("projects", project_id)


def list_projects() -> list[dict[str, Any]]:
    with sqlite3.connect(DATABASE_PATH) as db:
        rows = db.execute("SELECT payload FROM projects ORDER BY updated_at DESC").fetchall()
    return [json.loads(row[0]) for row in rows]


def save_entity(table: str, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    return _save(table, payload.get("id", new_id(table[:-1])), project_id, payload)


def get_entity(table: str, object_id: str) -> dict[str, Any] | None:
    return _get(table, object_id)


def list_entities(table: str, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return _list(table, project_id, limit)


def insert_packets(flight_id: str, packets: list[dict[str, Any]]) -> None:
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("DELETE FROM telemetry_packets WHERE flight_id = ?", (flight_id,))
        db.executemany("INSERT INTO telemetry_packets (flight_id, packet_number, timestamp_s, payload) VALUES (?, ?, ?, ?)", [(flight_id, packet["packet_number"], packet["timestamp_s"], json.dumps(packet)) for packet in packets])


def get_packets(flight_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(DATABASE_PATH) as db:
        rows = db.execute("SELECT payload FROM telemetry_packets WHERE flight_id = ? ORDER BY timestamp_s, packet_number", (flight_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_simulation(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    result = save_entity("simulation_runs", payload, project_id)
    telemetry = result.pop("telemetry", [])
    result["telemetry_count"] = len(telemetry)
    # Keep full telemetry in a dedicated table-shaped record for reuse.
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("UPDATE simulation_runs SET payload = ? WHERE id = ?", (json.dumps(result), result["id"]))
        db.execute("DELETE FROM telemetry_packets WHERE flight_id = ?", (result["id"],))
        db.executemany("INSERT INTO telemetry_packets (flight_id, packet_number, timestamp_s, payload) VALUES (?, ?, ?, ?)", [(result["id"], packet["packet_number"], packet["timestamp_s"], json.dumps(packet)) for packet in telemetry])
    return result


def simulation_with_packets(simulation_id: str) -> dict[str, Any] | None:
    result = _get("simulation_runs", simulation_id)
    if result:
        result["telemetry"] = get_packets(simulation_id)
    return result


def save_flight(payload: dict[str, Any], project_id: str, packets: list[dict[str, Any]]) -> dict[str, Any]:
    result = save_entity("flights", payload, project_id)
    insert_packets(result["id"], packets)
    return result


def flight_with_packets(flight_id: str) -> dict[str, Any] | None:
    result = _get("flights", flight_id)
    if result:
        result["telemetry"] = get_packets(flight_id)
    return result


def record_audit(event: AuditEvent) -> None:
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("INSERT INTO audit_events (occurred_at, actor, action, object_id, result, detail) VALUES (?, ?, ?, ?, ?, ?)", (event.occurred_at.isoformat(), event.actor, event.action, event.object_id, event.result, event.detail))


def audit_history(limit: int = 100) -> list[dict[str, Any]]:
    with sqlite3.connect(DATABASE_PATH) as db:
        rows = db.execute("SELECT occurred_at, actor, action, object_id, result, detail FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"occurred_at": row[0], "actor": row[1], "action": row[2], "object_id": row[3], "result": row[4], "detail": row[5]} for row in rows]


def latest_runs(project_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return list_entities("simulation_runs", project_id, limit)


def reset_project(project_id: str) -> None:
    """Delete only rows belonging to one project; never touches arbitrary files."""
    with sqlite3.connect(DATABASE_PATH) as db:
        for table in TABLES:
            if table == "telemetry_packets":
                continue
            if table == "audit_events":
                continue
            if table == "projects":
                continue
            db.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
        db.execute("DELETE FROM telemetry_packets WHERE flight_id NOT IN (SELECT id FROM flights UNION SELECT id FROM simulation_runs)")
