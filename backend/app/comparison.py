"""Simulation-vs-flight comparison and cautious discrepancy suggestions."""
from __future__ import annotations

from .models import ComparisonMetric, TelemetryPacket


def compare(simulation: list[TelemetryPacket], actual: list[TelemetryPacket]) -> dict:
    """Calculate headline mission metrics with configurable-style tolerance bands."""
    sim_apogee = max(simulation, key=lambda packet: packet.altitude_m)
    actual_apogee = max(actual, key=lambda packet: packet.altitude_m)
    metrics = [
        _metric("Max altitude", sim_apogee.altitude_m, actual_apogee.altitude_m, "m", 5),
        _metric("Apogee time", sim_apogee.timestamp_s, actual_apogee.timestamp_s, "s", 2),
        _metric("Temperature at apogee", sim_apogee.temperature_c, actual_apogee.temperature_c, "°C", 3),
        _metric("Telemetry packets", len(simulation), len(actual), "packets", 5),
    ]
    return {"metrics": metrics, "investigation_areas": ["Initial conditions", "Sensor calibration", "Atmospheric assumptions", "Vehicle mass/configuration", "Telemetry timing"], "note": "These are potential investigation areas, not asserted root causes."}


def _metric(name: str, simulation: float, actual: float, unit: str, tolerance_percent: float) -> ComparisonMetric:
    difference = actual - simulation
    percent = abs(difference / simulation * 100) if simulation else 0
    classification = "MATCH" if percent < 0.5 else "WITHIN TOLERANCE" if percent <= tolerance_percent else "WARNING" if percent <= tolerance_percent * 2 else "SIGNIFICANT DIFFERENCE"
    return ComparisonMetric(metric=name, simulation=round(simulation, 2), actual=round(actual, 2), difference=round(difference, 2), unit=unit, classification=classification)
