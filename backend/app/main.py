"""FastAPI application for the local Mission Validation Platform."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .comparison import compare
from .models import AuditEvent, CompareRequest, ConfigurationUpdate, CsvImport, FaultEvent, ProjectCreate, ScenarioRequest, ScanRequest, SecurityFinding, Severity, TestCaseCreate, new_id
from .ork import parse_ork
from .reports import build_report
from .security import scan_text
from .simulator import simulate, verify_packet
from .storage import audit_history, flight_with_packets, get_entity, get_packets, get_project, initialize, latest_runs, list_entities, list_projects, record_audit, reset_project, save_entity, save_flight, save_project, save_simulation, simulation_with_packets
from .telemetry import parse_csv, telemetry_stats

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DEMO = ROOT / "demo"
REPORTS = ROOT / "data" / "reports"
DEMO_PROJECT_ID = "project-demo-2026"

app = FastAPI(title="Mission Validation Platform", version="0.2.0", description="Local-first student rocketry validation prototype. Synthetic simulation only; not flight certification.")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_project() -> dict[str, Any]:
    projects = list_projects()
    if not projects:
        raise HTTPException(status_code=404, detail="No project exists. Create a project or seed demo data.")
    return projects[0]


def _json_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def seed_demo() -> dict[str, Any]:
    """Insert the demo through the same persistence paths used by user data."""
    existing = get_project(DEMO_PROJECT_ID)
    if existing and list_entities("missions", DEMO_PROJECT_ID, 1):
        return existing
    project = save_project({"id": DEMO_PROJECT_ID, "name": "IN-SPACe Rocket 2026", "vehicle_name": "Team Falcon-X", "mission_name": "1000 m target altitude", "version": "0.1", "source": "seed"}, DEMO_PROJECT_ID)
    save_entity("vehicles", {"id": "vehicle-demo-falcon-x", "name": "Team Falcon-X", "mass_kg": 1.82, "length_m": 1.38, "stages": 1, "motor": "Demo solid motor", "components": [{"id": "body", "type": "RocketBody", "label": "Body tube", "position_m": 0.48, "length_m": 0.92, "radius_m": 0.045, "mass_kg": 0.52}, {"id": "nose", "type": "NoseCone", "label": "Nose cone", "position_m": 1.01, "length_m": 0.37, "radius_m": 0.045, "mass_kg": 0.16}, {"id": "payload", "type": "PayloadSection", "label": "7U CanSat payload", "position_m": 0.68, "length_m": 0.25, "radius_m": 0.04, "mass_kg": 0.70}, {"id": "motor", "type": "MotorSection", "label": "Motor section", "position_m": 0.12, "length_m": 0.22, "radius_m": 0.043, "mass_kg": 0.44}, {"id": "fins", "type": "FinSet", "label": "Three fins", "position_m": 0.22, "root_m": 0.25, "span_m": 0.12, "count": 3, "mass_kg": 0.08}], "cg_m": 0.58, "cp_m": 0.72, "source": "demo/rocket.ork"}, DEMO_PROJECT_ID)
    mission = {"id": "mission-demo-1000m", "name": "1000 m target altitude", "target_altitude_m": 1000, "allowed_altitude_error_m": 100, "telemetry_rate_hz": 1, "expected_duration_s": 90, "sensors": {"pressure": True, "temperature": True, "gps": True, "battery": True}, "version": "v1.7"}
    save_entity("missions", mission, DEMO_PROJECT_ID)
    save_entity("config_revisions", {"id": "revision-demo-v1-7", "version": "v1.7", "reason": "Rocket mass changed by +80 g", "diff": {"mass_kg": {"before": 1.74, "after": 1.82}}, "source": "seed"}, DEMO_PROJECT_ID)
    ork = DEMO / "rocket.ork"
    actual = DEMO / "actual_flight.csv"
    simulated = DEMO / "simulated_flight.csv"
    for path, kind in [(ork, "openrocket"), (actual, "telemetry"), (simulated, "telemetry")]:
        content = path.read_bytes()
        save_entity("artifacts", {"id": new_id("artifact"), "name": path.name, "kind": kind, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content), "source": f"demo/{path.name}", "preview": "Parsed metadata" if kind == "openrocket" else "CSV telemetry"}, DEMO_PROJECT_ID)
    packets, errors, _ = parse_csv(_json_file(actual))
    save_flight({"id": "flight-demo-003", "name": "Flight 003", "type": "REAL", "source": "demo/actual_flight.csv", "source_sha256": hashlib.sha256(actual.read_bytes()).hexdigest(), "validation_errors": errors, "available_fields": ["packet_number", "timestamp_s", "altitude_m", "temperature_c", "battery_v", "phase", "gps_valid"], "stats": telemetry_stats(packets)}, DEMO_PROJECT_ID, [packet.model_dump(mode="json") for packet in packets])
    sim = simulate(ScenarioRequest(name="Simulation #12", target_altitude_m=1000, duration_s=90, sample_rate_hz=1, seed=2026))
    sim_payload = sim.model_dump(mode="json")
    sim_payload["project_id"] = DEMO_PROJECT_ID
    save_simulation(sim_payload, DEMO_PROJECT_ID)
    for event in [{"type": "GPS_LOSS", "start_s": 40, "duration_s": 10, "severity": "MEDIUM"}, {"type": "RADIO_LOSS", "start_s": 40, "duration_s": 5, "severity": "HIGH"}]:
        save_entity("scenarios", {"id": new_id("scenario"), "name": event["type"], "events": [event], "source": "seed"}, DEMO_PROJECT_ID)
    tests = [{"id": "TEST-MSN-001", "name": "Normal mission", "scenario": ScenarioRequest(name="Normal mission").model_dump(mode="json"), "expected_behavior": "Mission reaches apogee and lands", "tolerance": 5}, {"id": "TEST-GPS-002", "name": "GPS loss", "scenario": ScenarioRequest(name="GPS loss", fault="gps_loss").model_dump(mode="json"), "expected_behavior": "Mission continues and GPS becomes invalid", "tolerance": 0}, {"id": "TEST-COM-004", "name": "Radio interruption", "scenario": ScenarioRequest(name="Radio interruption", fault="radio_loss").model_dump(mode="json"), "expected_behavior": "Reconnect within 3 seconds", "tolerance": 3}, {"id": "TEST-TEL-006", "name": "Malformed telemetry", "scenario": ScenarioRequest(name="Malformed telemetry", fault="malformed_packet").model_dump(mode="json"), "expected_behavior": "Malformed packets are rejected", "tolerance": 0}]
    for test in tests:
        save_entity("test_cases", test, DEMO_PROJECT_ID)
    save_entity("requirements", {"id": "REQ-TEL-001", "requirement": "Telemetry transmitted at 1 Hz", "implementation": "telemetry.py", "test": "TEST-MSN-001", "evidence": "flight-demo-003", "status": "VERIFIED"}, DEMO_PROJECT_ID)
    save_entity("requirements", {"id": "REQ-COM-004", "requirement": "Detect missing telemetry and recover within 3 seconds", "implementation": "telemetry.py", "test": "TEST-COM-004", "evidence": "scenario radio loss", "status": "FAILED"}, DEMO_PROJECT_ID)
    finding = SecurityFinding(id="SEC-001", title="Malformed packet rejected", severity="LOW", status="RESOLVED", detail="Schema validation rejected an invalid packet; source data was unchanged.")
    save_entity("security_findings", finding.model_dump(mode="json"), DEMO_PROJECT_ID)
    record_audit(AuditEvent(action="project_seeded", result="PASS", detail="Seeded Falcon-X demo through normal persistence paths.", object_id=DEMO_PROJECT_ID))
    return project


@app.on_event("startup")
def startup() -> None:
    initialize()
    seed_demo()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    return list_projects()


@app.post("/api/projects")
def create_project(payload: ProjectCreate) -> dict[str, Any]:
    project_id = new_id("project")
    project = save_project({"id": project_id, "name": payload.name, "vehicle_name": payload.vehicle_name, "mission_name": payload.mission_name, "version": "v1.0", "source": "user"}, project_id)
    save_entity("vehicles", {"id": new_id("vehicle"), "name": payload.vehicle_name, "mass_kg": 0, "length_m": 0, "stages": 1, "components": [], "source": "project form"}, project_id)
    save_entity("missions", {"id": new_id("mission"), "name": payload.mission_name, "target_altitude_m": payload.target_altitude_m, "allowed_altitude_error_m": payload.target_altitude_m * .1, "telemetry_rate_hz": payload.telemetry_rate_hz, "expected_duration_s": payload.expected_duration_s, "version": "v1.0"}, project_id)
    save_entity("config_revisions", {"id": new_id("revision"), "version": "v1.0", "reason": "Project created", "diff": {}, "source": "user"}, project_id)
    record_audit(AuditEvent(action="project_created", result="PASS", detail=f"Created project {payload.name}.", object_id=project_id))
    return project


@app.get("/api/projects/{project_id}")
def project_detail(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project, "vehicle": get_entity("vehicles", list_entities("vehicles", project_id, 1)[0]["id"]) if list_entities("vehicles", project_id, 1) else None, "mission": list_entities("missions", project_id, 1)[0] if list_entities("missions", project_id, 1) else None}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    project = current_project()
    project_id = project["id"]
    mission = list_entities("missions", project_id, 1)[0]
    vehicles = list_entities("vehicles", project_id, 1)
    flights = list_entities("flights", project_id, 20)
    simulations = latest_runs(project_id, 20)
    test_runs = list_entities("test_runs", project_id, 1)
    findings = list_entities("security_findings", project_id, 100)
    passed = test_runs[0].get("passed", 0) if test_runs else 0
    total_tests = test_runs[0].get("total", 0) if test_runs else len(list_entities("test_cases", project_id, 100))
    test_rate = (passed / total_tests) if total_tests else 0
    telemetry_quality = 1 if flights and not flights[0].get("validation_errors") else .8 if flights else 0
    security_score = 1 if not any(f.get("severity") == "HIGH" and f.get("status") == "OPEN" for f in findings) else .5
    score = round((min(1, len(simulations) / 1) * 20) + test_rate * 30 + telemetry_quality * 20 + (1 if list_entities("config_revisions", project_id, 1) else 0) * 15 + security_score * 15)
    latest_flight = flights[0] if flights else None
    latest_sim = simulations[0] if simulations else None
    return {"project": project, "mission": mission, "vehicle": vehicles[0] if vehicles else None, "latest_flight": latest_flight, "latest_simulation": {"id": latest_sim["id"], "stats": {"packets": latest_sim.get("telemetry_count", 0)}} if latest_sim else None, "health": {"score": score, "summary": "Calculated from simulation coverage, test pass rate, telemetry quality, traceability, and security findings.", "breakdown": {"simulation_coverage": min(20, len(simulations) * 20), "test_pass_rate": round(test_rate * 30), "telemetry_quality": round(telemetry_quality * 20), "configuration_traceability": 15 if list_entities("config_revisions", project_id, 1) else 0, "security": round(security_score * 15)}, "items": [{"name": "Simulation", "status": "GOOD" if simulations else "NOT TESTED"}, {"name": "Telemetry", "status": "GOOD" if flights else "NOT TESTED"}, {"name": "Testing", "status": "GOOD" if total_tests and passed == total_tests else "WARNING" if total_tests else "NOT TESTED"}, {"name": "Configuration", "status": "GOOD" if list_entities("config_revisions", project_id, 1) else "NOT TESTED"}, {"name": "Cybersecurity", "status": "GOOD" if security_score == 1 else "WARNING"}]}, "next_investigation": "Review radio recovery timing" if test_runs and test_runs[0].get("failed") else "Run the first validation suite"}


@app.get("/api/vehicle")
def vehicle() -> dict[str, Any]:
    project = current_project()
    records = list_entities("vehicles", project["id"], 1)
    if not records:
        raise HTTPException(status_code=404, detail="Vehicle not configured")
    return records[0]


@app.post("/api/artifacts/import")
def import_artifact(payload: CsvImport) -> dict[str, Any]:
    project = current_project()
    safe_name = Path(payload.name).name
    content_bytes = payload.csv.encode()
    artifact = save_entity("artifacts", {"id": new_id("artifact"), "name": safe_name, "kind": "openrocket" if safe_name.lower().endswith(".ork") else "artifact", "sha256": hashlib.sha256(content_bytes).hexdigest(), "size_bytes": len(content_bytes), "source": "user import"}, project["id"])
    normalized = parse_ork(payload.csv) if safe_name.lower().endswith(".ork") else {"warnings": ["Preview unavailable. File retained for project traceability."]}
    record_audit(AuditEvent(action="artifact_imported", result="PASS", detail=f"Imported {safe_name} with SHA-256 {artifact['sha256'][:12]}…", object_id=artifact["id"]))
    return {"artifact": artifact, "normalized_vehicle": normalized}


@app.get("/api/artifacts")
def artifacts() -> list[dict[str, Any]]:
    return list_entities("artifacts", current_project()["id"], 100)


@app.post("/api/simulate")
def run_simulation(request: ScenarioRequest) -> dict[str, Any]:
    project = current_project()
    result = simulate(request)
    payload = result.model_dump(mode="json")
    payload["project_id"] = project["id"]
    payload["stats"] = telemetry_stats(result.telemetry)
    save_simulation(payload, project["id"])
    save_entity("scenarios", {"id": new_id("scenario"), "name": request.name, "events": [event.model_dump(mode="json") for event in request.normalized_events()], "source": "simulation request"}, project["id"])
    record_audit(AuditEvent(action="simulation_run", result=result.verdict.value, detail=f"{request.name}; seed {request.seed}; {len(result.telemetry)} packets", object_id=result.id))
    return payload


@app.get("/api/simulations")
def simulations() -> list[dict[str, Any]]:
    return latest_runs(current_project()["id"], 100)


@app.get("/api/simulations/{simulation_id}")
def simulation_detail(simulation_id: str) -> dict[str, Any]:
    result = simulation_with_packets(simulation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return result


def execute_test(test: dict[str, Any]) -> dict[str, Any]:
    scenario = ScenarioRequest.model_validate(test["scenario"])
    simulation = simulate(scenario)
    expected = test["expected_behavior"].lower()
    if "gps" in test["name"].lower():
        passed = simulation.validation["gps_unavailable_samples"] > 0 and all(not packet.gps_valid for packet in simulation.telemetry if scenario.start_s <= packet.timestamp_s < scenario.start_s + 5)
    elif "malformed" in test["name"].lower():
        passed = simulation.validation["rejected_packets"] > 0
    elif "radio" in test["name"].lower():
        passed = simulation.validation["radio_recovery_s"] <= float(test.get("tolerance", 3))
    else:
        passed = simulation.verdict == Severity.GOOD and max(packet.altitude_m for packet in simulation.telemetry) >= scenario.target_altitude_m * .95
    return {"test_case_id": test["id"], "name": test["name"], "result": "PASS" if passed else "FAIL", "expected": expected, "actual": simulation.validation}


@app.get("/api/tests")
def tests() -> list[dict[str, Any]]:
    return list_entities("test_cases", current_project()["id"], 100)


@app.post("/api/tests")
def create_test(payload: TestCaseCreate) -> dict[str, Any]:
    project = current_project()
    test = {"id": new_id("test"), "name": payload.name, "scenario": payload.scenario.model_dump(mode="json"), "expected_behavior": payload.expected_behavior, "tolerance": payload.tolerance, "source": "user"}
    save_entity("test_cases", test, project["id"])
    record_audit(AuditEvent(action="test_case_created", result="PASS", detail=payload.name, object_id=test["id"]))
    return test


@app.post("/api/tests/run")
def run_tests() -> dict[str, Any]:
    project = current_project()
    cases = list_entities("test_cases", project["id"], 100)
    outcomes = [execute_test(test) for test in cases]
    passed = sum(outcome["result"] == "PASS" for outcome in outcomes)
    failed = len(outcomes) - passed
    run = {"id": new_id("test-run"), "total": len(outcomes), "passed": passed, "warnings": 0, "failed": failed, "cases": outcomes, "headline": "All registered tests passed." if failed == 0 else f"{failed} registered test(s) failed.", "created_at": now()}
    save_entity("test_runs", run, project["id"])
    record_audit(AuditEvent(action="missiontest_run", result="PASS" if failed == 0 else "FAIL", detail=run["headline"], object_id=run["id"]))
    return run


@app.get("/api/flights")
def flights() -> dict[str, Any]:
    return {"flights": list_entities("flights", current_project()["id"], 100), "replay": {"available": True, "controls": ["Play", "Pause", "Restart", "0.25×", "0.5×", "1×", "2×", "4×", "10×", "Timeline seek"]}}


@app.get("/api/flights/{flight_id}")
def flight_detail(flight_id: str) -> dict[str, Any]:
    flight = flight_with_packets(flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


@app.get("/api/datasets")
def datasets() -> dict[str, Any]:
    project_id = current_project()["id"]
    return {"simulations": [{"id": item["id"], "name": item.get("scenario", {}).get("name", item["id"]), "stats": item.get("stats", {})} for item in latest_runs(project_id, 100)], "flights": list_entities("flights", project_id, 100)}


@app.post("/api/telemetry/import")
def import_telemetry(payload: CsvImport) -> dict[str, Any]:
    project = current_project()
    packets, errors, mapping = parse_csv(payload.csv, payload.mapping)
    if not payload.confirm_mapping:
        return {"stage": "mapping", "file": Path(payload.name).name, "suggested_mapping": mapping, "errors": errors, "sample_packets": [packet.model_dump(mode="json") for packet in packets[:3]], "message": "Review the suggested mapping and confirm before storing this flight."}
    if not packets:
        raise HTTPException(status_code=422, detail="Could not store flight: no valid telemetry rows were found.")
    safe_name = Path(payload.name).name
    artifact = save_entity("artifacts", {"id": new_id("artifact"), "name": safe_name, "kind": "telemetry", "sha256": hashlib.sha256(payload.csv.encode()).hexdigest(), "size_bytes": len(payload.csv.encode()), "source": "user import", "column_mapping": mapping}, project["id"])
    flight_id = new_id("flight")
    flight = save_flight({"id": flight_id, "name": Path(safe_name).stem, "type": "REAL", "source": safe_name, "source_sha256": artifact["sha256"], "imported_at": now(), "column_mapping": mapping, "available_fields": sorted(set(mapping.values()) | {"phase"}), "validation_errors": errors, "stats": telemetry_stats(packets)}, project["id"], [packet.model_dump(mode="json") for packet in packets])
    record_audit(AuditEvent(action="flight_imported", result="PASS" if not errors else "WARNING", detail=f"Stored {len(packets)} packets from {safe_name}; {len(errors)} rejected rows.", object_id=flight_id))
    return {"stage": "stored", "flight": flight, "packets": len(packets), "errors": errors, "suggested_mapping": mapping, "message": "Flight is now available to replay, compare, and report."}


@app.post("/api/telemetry/verify")
def verify_telemetry(packet: dict[str, Any]) -> dict[str, bool]:
    """Validate an HMAC-bearing packet and make tampering visible to clients."""
    from .models import TelemetryPacket
    try:
        parsed = TelemetryPacket.model_validate(packet)
    except Exception:
        return {"valid": False}
    valid = verify_packet(parsed)
    record_audit(AuditEvent(action="telemetry_integrity_check", result="PASS" if valid else "FAIL", detail="Packet signature verification."))
    return {"valid": valid}


@app.get("/api/compare")
def default_compare() -> dict[str, Any]:
    data = datasets()
    if not data["simulations"] or not data["flights"]:
        raise HTTPException(status_code=404, detail="Create a simulation and import a flight before comparing.")
    return selected_compare(CompareRequest(simulation_id=data["simulations"][0]["id"], flight_id=data["flights"][0]["id"]))


@app.post("/api/compare")
def selected_compare(request: CompareRequest) -> dict[str, Any]:
    simulation = simulation_with_packets(request.simulation_id)
    flight = flight_with_packets(request.flight_id)
    if not simulation or not flight:
        raise HTTPException(status_code=404, detail="Selected simulation or flight was not found.")
    result = compare(simulation["telemetry"], flight["telemetry"], actual_fields=set(flight.get("available_fields", [])) or None)
    result["simulation_id"] = request.simulation_id
    result["flight_id"] = request.flight_id
    record_audit(AuditEvent(action="comparison_run", result="PASS", detail=f"Compared {request.simulation_id} with {request.flight_id}."))
    return result


@app.get("/api/mission/config")
def mission_config() -> dict[str, Any]:
    records = list_entities("missions", current_project()["id"], 1)
    if not records:
        raise HTTPException(status_code=404, detail="Mission configuration not found")
    return records[0]


@app.post("/api/mission/config")
def update_mission_config(request: ConfigurationUpdate) -> dict[str, Any]:
    project = current_project()
    mission = mission_config()
    version_number = int(str(mission.get("version", "v1.0")).lstrip("v").split(".")[0]) + 1
    version = f"v{version_number}.0"
    changed = {field: {"before": mission.get(field), "after": getattr(request, field)} for field in ["target_altitude_m", "telemetry_rate_hz", "expected_duration_s"] if mission.get(field) != getattr(request, field)}
    updated = {**mission, "target_altitude_m": request.target_altitude_m, "telemetry_rate_hz": request.telemetry_rate_hz, "expected_duration_s": request.expected_duration_s, "version": version}
    save_entity("missions", updated, project["id"])
    save_entity("config_revisions", {"id": new_id("revision"), "version": version, "reason": request.reason, "diff": changed, "source": "user"}, project["id"])
    record_audit(AuditEvent(action="configuration_changed", result="PASS", detail=request.reason, object_id=mission["id"]))
    return updated


@app.get("/api/config/history")
def configuration_history() -> dict[str, Any]:
    records = list_entities("config_revisions", current_project()["id"], 100)
    return {"current": mission_config().get("version", "v1.0"), "revisions": records}


@app.get("/api/requirements")
def requirements() -> list[dict[str, Any]]:
    return list_entities("requirements", current_project()["id"], 100)


@app.get("/api/security/findings")
def security_findings() -> list[dict[str, Any]]:
    return list_entities("security_findings", current_project()["id"], 100)


@app.post("/api/security/scan")
def security_scan(request: ScanRequest) -> list[dict[str, Any]]:
    project = current_project()
    findings = scan_text(request.name, request.content)
    stored = []
    for finding in findings:
        item = save_entity("security_findings", finding.model_dump(mode="json"), project["id"])
        stored.append(item)
    record_audit(AuditEvent(action="security_scan", result="WARNING" if findings else "PASS", detail=f"Scanned {Path(request.name).name}; {len(findings)} potential findings."))
    return stored


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    return latest_runs(current_project()["id"])


@app.get("/api/audit")
def audit() -> list[dict[str, Any]]:
    return audit_history()


@app.post("/api/reports")
def generate_report(request: CompareRequest | None = None) -> dict[str, Any]:
    project = current_project()
    data = datasets()
    if not data["simulations"] or not data["flights"]:
        raise HTTPException(status_code=422, detail="Report requires at least one simulation and one flight.")
    selection = request or CompareRequest(simulation_id=data["simulations"][0]["id"], flight_id=data["flights"][0]["id"])
    comparison = selected_compare(selection)
    test_records = list_entities("test_runs", project["id"], 1)
    tests = test_records[0] if test_records else {"total": 0, "passed": 0, "warnings": 0, "failed": 0, "headline": "MissionTest has not run."}
    path_id = new_id("report")
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{path_id}.html"
    path.write_text(build_report(dashboard(), comparison, tests), encoding="utf-8")
    report = save_entity("reports", {"id": path_id, "format": "HTML", "path": str(path), "simulation_id": selection.simulation_id, "flight_id": selection.flight_id, "generated_at": now()}, project["id"])
    record_audit(AuditEvent(action="report_generated", result="PASS", detail="Generated report from current persisted data.", object_id=path_id))
    return {"id": path_id, "url": f"/api/reports/{path_id}", "formats": ["HTML", "JSON"], "report": report}


@app.get("/api/reports/{report_id}", response_class=HTMLResponse)
def get_report(report_id: str) -> FileResponse:
    report = get_entity("reports", report_id)
    if not report or not Path(report["path"]).exists():
        raise HTTPException(status_code=404, detail="Report not found. Generate it first.")
    return FileResponse(report["path"], media_type="text/html", filename=f"{report_id}.html")


@app.post("/api/demo/reset")
def reset_demo() -> dict[str, Any]:
    reset_project(DEMO_PROJECT_ID)
    record_audit(AuditEvent(action="demo_reset", result="PASS", detail="Deleted and reseeded only the demo project.", object_id=DEMO_PROJECT_ID))
    return seed_demo()
