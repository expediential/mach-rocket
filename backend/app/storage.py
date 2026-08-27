"""Minimal SQLite audit store for local reproducibility records."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import AuditEvent, SimulationResult

DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "mission_validation.db"


def initialize() -> None:
    """Create the local audit tables when the application starts."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, occurred_at TEXT, actor TEXT, action TEXT, result TEXT, detail TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS simulation_runs (id TEXT PRIMARY KEY, created_at TEXT, scenario TEXT, seed INTEGER, configuration_version TEXT, software_version TEXT, verdict TEXT, result_json TEXT)")


def record_audit(event: AuditEvent) -> None:
    """Append an audit event; this local prototype has no user authentication."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("INSERT INTO audit_events (occurred_at, actor, action, result, detail) VALUES (?, ?, ?, ?, ?)", (event.occurred_at.isoformat(), event.actor, event.action, event.result, event.detail))


def save_simulation(result: SimulationResult) -> None:
    """Persist a reproducible run record including scenario seed and configuration."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("INSERT OR REPLACE INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (result.id, result.created_at.isoformat(), result.scenario.name, result.scenario.seed, result.configuration_version, result.software_version, result.verdict.value, result.model_dump_json()))


def audit_history(limit: int = 20) -> list[dict]:
    """Return recent audit records in reverse chronological order."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute("SELECT occurred_at, actor, action, result, detail FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"occurred_at": row[0], "actor": row[1], "action": row[2], "result": row[3], "detail": row[4]} for row in rows]


def latest_runs(limit: int = 10) -> list[dict]:
    """Return run summaries without shipping full telemetry arrays."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute("SELECT id, created_at, scenario, seed, configuration_version, software_version, verdict FROM simulation_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": row[0], "created_at": row[1], "scenario": row[2], "seed": row[3], "configuration_version": row[4], "software_version": row[5], "verdict": row[6]} for row in rows]
