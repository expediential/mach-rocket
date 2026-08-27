"""Local FastAPI entrypoint for the Mission Validation Platform prototype."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .comparison import compare
from .models import AuditEvent, MissionPhase, ScenarioRequest, SecurityFinding, Severity, TelemetryPacket
from .reports import build_report
from .security import demo_findings, scan_text
from .simulator import altitude, mission_phase, simulate
from .storage import audit_history, initialize, latest_runs, record_audit, save_simulation
from .telemetry import parse_csv

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
REPORTS = ROOT / "data" / "reports"

app = FastAPI(title="Mission Validation Platform", version="0.1.0", description="Local-first student rocketry validation prototype. Synthetic simulation only; not flight certification.")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


class CsvImport(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    csv: str = Field(max_length=1_000_000)


class ScanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    content: str = Field(max_length=200_000)


def actual_flight() -> list[TelemetryPacket]:
    """Return included Flight 003 telemetry with its documented 967 m apogee."""
    packets = []
    for second in range(91):
        base = altitude(second) * 0.967
        packets.append(TelemetryPacket(packet_number=second, timestamp_s=float(second), altitude_m=round(base, 2), velocity_m_s=0, pressure_hpa=round(1013.25 * (1 - base / 8434.5), 2), temperature_c=round(24 - base * .0062, 2), battery_v=round(8.4 - second * .012, 3), latitude=12.9716, longitude=77.5946, phase=mission_phase(second)))
    return packets[:-4]


def test_summary() -> dict:
    """Return the demo MissionTest evidence, including the prescribed radio failure."""
    return {"total": 30, "passed": 26, "warnings": 3, "failed": 1, "headline": "Radio-loss recovery did not recover within the expected 3-second timeout.", "cases": [{"id": "TEST-MSN-001", "name": "Normal mission", "result": "PASS", "detail": "Mission reached simulated apogee and landed."}, {"id": "TEST-GPS-002", "name": "GPS loss", "result": "PASS", "detail": "Mission continued and GPS was marked invalid."}, {"id": "TEST-COM-004", "name": "5-second radio interruption", "result": "FAIL", "detail": "Reconnect observed at 5 seconds; expected no more than 3 seconds."}, {"id": "TEST-TEL-006", "name": "Malformed telemetry", "result": "PASS", "detail": "Invalid packet was rejected before dashboard storage."}]}


def dashboard() -> dict:
    """Assemble the clear, student-readable demo landing data."""
    return {"project": {"id": "demo-2026", "name": "IN-SPACe Rocket 2026", "vehicle": "Team Falcon-X", "version": "0.1"}, "mission": {"name": "1000 m target altitude", "target_altitude_m": 1000, "allowed_error_m": 100, "telemetry_rate_hz": 1, "expected_duration_s": 90}, "health": {"score": 82, "summary": "Software verification health indicator — lowered by radio recovery failure and comparison warning.", "items": [{"name": "Simulation", "status": "GOOD"}, {"name": "Telemetry", "status": "GOOD"}, {"name": "Testing", "status": "WARNING"}, {"name": "Configuration", "status": "GOOD"}, {"name": "Cybersecurity", "status": "GOOD"}]}, "next_investigation": "Investigate radio reconnection timing before the next test flight."}


@app.on_event("startup")
def startup() -> None:
    initialize()
    record_audit(AuditEvent(action="demo_project_loaded", result="PASS", detail="Loaded IN-SPACe Rocket 2026 starter project."))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/dashboard")
def get_dashboard() -> dict:
    return dashboard()


@app.get("/api/vehicle")
def get_vehicle() -> dict:
    return {"name": "Team Falcon-X", "source": "demo/rocket.ork", "mass_kg": 1.82, "length_m": 1.38, "stages": 1, "motor": "Demo solid motor", "view": "Simplified procedural technical representation; source OpenRocket artifact is retained unchanged."}


@app.get("/api/artifacts")
def artifacts() -> list[dict]:
    return [{"name": "rocket.ork", "type": "OpenRocket design", "status": "Imported", "preview": "Parsed metadata"}, {"name": "mission.yaml", "type": "Mission configuration", "status": "v1.7", "preview": "Human-readable source of truth"}, {"name": "actual_flight.csv", "type": "Telemetry", "status": "Flight 003", "preview": "Ready for replay/comparison"}]


@app.post("/api/simulate")
def run_simulation(request: ScenarioRequest) -> dict:
    result = simulate(request)
    save_simulation(result)
    record_audit(AuditEvent(action="simulation_run", result=result.verdict.value, detail=f"{request.name}; seed {request.seed}; fault {request.fault}"))
    return result.model_dump(mode="json")


@app.post("/api/tests/run")
def run_tests() -> dict:
    result = test_summary()
    record_audit(AuditEvent(action="missiontest_run", result="FAIL", detail=result["headline"]))
    return result


@app.get("/api/flights")
def flights() -> dict:
    return {"flights": [{"id": "flight-003", "type": "REAL FLIGHT", "name": "Flight 003", "max_altitude_m": 967, "duration_s": 86, "packets": 87}, {"id": "sim-demo", "type": "SIMULATED FLIGHT", "name": "Simulation #12", "max_altitude_m": 1000, "duration_s": 90, "packets": 91}], "replay": {"available": True, "controls": ["Play", "Pause", "Replay", "Fast-forward", "Slow-motion", "Jump to timestamp"]}}


@app.get("/api/compare")
def get_comparison() -> dict:
    result = compare(simulate(ScenarioRequest()).telemetry, actual_flight())
    record_audit(AuditEvent(action="comparison_viewed", result="WARNING", detail="Simulation #12 compared with Flight 003."))
    return result


@app.post("/api/telemetry/import")
def import_telemetry(payload: CsvImport) -> dict:
    packets, errors, mapping = parse_csv(payload.csv)
    result = "PASS" if not errors else "WARNING"
    record_audit(AuditEvent(action="telemetry_import", result=result, detail=f"{payload.name}: {len(packets)} valid packets, {len(errors)} rejected rows."))
    return {"file": Path(payload.name).name, "packets": len(packets), "errors": errors, "suggested_mapping": mapping, "message": "No source data was modified."}


@app.get("/api/config/history")
def configuration_history() -> dict:
    return {"current": "v1.7", "revisions": [{"version": "v1.7", "change": "Rocket mass changed by +80 g", "effect": "Simulation error increased", "timestamp": "2026-08-27T09:30:00Z"}, {"version": "v1.6", "change": "Target altitude tolerance set to ±100 m", "effect": "Baseline", "timestamp": "2026-08-20T11:00:00Z"}]}


@app.get("/api/security/findings")
def security_findings() -> list[SecurityFinding]:
    return demo_findings()


@app.post("/api/security/scan")
def security_scan(payload: ScanRequest) -> list[SecurityFinding]:
    findings = scan_text(payload.name, payload.content)
    record_audit(AuditEvent(action="security_scan", result="WARNING" if findings else "PASS", detail=f"Scanned {Path(payload.name).name}; {len(findings)} potential findings."))
    return findings


@app.get("/api/runs")
def runs() -> list[dict]:
    return latest_runs()


@app.get("/api/audit")
def audit() -> list[dict]:
    return audit_history()


@app.post("/api/reports")
def generate_report() -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "mission-validation-report.html"
    path.write_text(build_report(dashboard(), compare(simulate(ScenarioRequest()).telemetry, actual_flight()), test_summary()), encoding="utf-8")
    record_audit(AuditEvent(action="report_generated", result="PASS", detail="Generated local HTML mission validation report."))
    return {"id": "report-demo", "url": "/api/reports/report-demo", "formats": ["HTML", "JSON"]}


@app.get("/api/reports/{report_id}", response_class=HTMLResponse)
def get_report(report_id: str) -> FileResponse:
    path = REPORTS / "mission-validation-report.html"
    if report_id != "report-demo" or not path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Generate the report first.")
    return FileResponse(path, media_type="text/html", filename="mission-validation-report.html")
