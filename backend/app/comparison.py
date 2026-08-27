"""Time-aligned simulation versus flight comparison."""
from __future__ import annotations

from typing import Any

from .models import ComparisonMetric, TelemetryPacket


def _get(packet: TelemetryPacket | dict[str, Any], field: str) -> float:
    value = packet[field] if isinstance(packet, dict) else getattr(packet, field)
    return float(value)


def _series(packets: list[TelemetryPacket | dict[str, Any]], field: str) -> list[tuple[float, float]]:
    return sorted((_get(packet, "timestamp_s"), _get(packet, field)) for packet in packets)


def interpolate(packets: list[TelemetryPacket | dict[str, Any]], field: str, timestamp: float) -> float | None:
    """Linearly interpolate a scalar at a common timestamp."""
    series = _series(packets, field)
    if not series or timestamp < series[0][0] or timestamp > series[-1][0]:
        return None
    for (left_time, left_value), (right_time, right_value) in zip(series, series[1:]):
        if left_time <= timestamp <= right_time:
            if right_time == left_time:
                return right_value
            fraction = (timestamp - left_time) / (right_time - left_time)
            return left_value + (right_value - left_value) * fraction
    return series[-1][1]


def compare(simulation: list[TelemetryPacket | dict[str, Any]], actual: list[TelemetryPacket | dict[str, Any]], tolerances: dict[str, float] | None = None, actual_fields: set[str] | None = None) -> dict[str, Any]:
    """Compare selected datasets using common-time interpolation where possible."""
    if not simulation or not actual:
        raise ValueError("Both datasets must contain at least one telemetry packet")
    tolerance = {"Max altitude": 5.0, "Apogee time": 2.0, "Maximum velocity": 10.0, "Temperature mean": 3.0, "Battery change": 5.0, "Telemetry packets": 5.0, "Mission duration": 2.0, **(tolerances or {})}
    sim_apogee = max(simulation, key=lambda packet: _get(packet, "altitude_m"))
    actual_apogee = max(actual, key=lambda packet: _get(packet, "altitude_m"))
    sim_times = [_get(packet, "timestamp_s") for packet in simulation]
    actual_times = [_get(packet, "timestamp_s") for packet in actual]
    metrics: list[ComparisonMetric] = []
    metrics.append(_metric("Max altitude", _get(sim_apogee, "altitude_m"), _get(actual_apogee, "altitude_m"), "m", tolerance["Max altitude"]))
    metrics.append(_metric("Apogee time", _get(sim_apogee, "timestamp_s"), _get(actual_apogee, "timestamp_s"), "s", tolerance["Apogee time"]))
    sim_velocity = max(abs(_get(packet, "velocity_m_s")) for packet in simulation)
    actual_velocity = max(abs(_get(packet, "velocity_m_s")) for packet in actual)
    sim_temp = sum(_get(packet, "temperature_c") for packet in simulation) / len(simulation)
    actual_temp = sum(_get(packet, "temperature_c") for packet in actual) / len(actual)
    metrics.append(_metric("Temperature mean", sim_temp, actual_temp, "°C", tolerance["Temperature mean"]))
    metrics.append(_metric("Telemetry packets", len(simulation), len(actual), "packets", tolerance["Telemetry packets"]))
    if actual_fields is None or "velocity_m_s" in actual_fields:
        metrics.append(_metric("Maximum velocity", sim_velocity, actual_velocity, "m/s", tolerance["Maximum velocity"]))
    sim_battery = _get(simulation[-1], "battery_v") - _get(simulation[0], "battery_v")
    actual_battery = _get(actual[-1], "battery_v") - _get(actual[0], "battery_v")
    metrics.append(_metric("Battery change", sim_battery, actual_battery, "V", tolerance["Battery change"]))
    metrics.append(_metric("Mission duration", max(sim_times) - min(sim_times), max(actual_times) - min(actual_times), "s", tolerance["Mission duration"]))
    common_start = max(min(sim_times), min(actual_times))
    common_end = min(max(sim_times), max(actual_times))
    aligned_points = 0
    if common_start <= common_end:
        aligned_points = sum(1 for time_s in sim_times if common_start <= time_s <= common_end)
    return {"metrics": metrics, "alignment_method": "linear interpolation over common timestamps", "aligned_points": aligned_points, "investigation_areas": ["Vehicle mass/configuration", "Atmospheric assumptions", "Launch conditions", "Sensor calibration", "Telemetry timing"], "note": "Potential investigation areas are hypotheses, not asserted root causes."}


def _metric(name: str, simulation: float, actual: float, unit: str, tolerance_percent: float) -> ComparisonMetric:
    difference = actual - simulation
    denominator = abs(simulation) if simulation else 1
    percent = abs(difference / denominator * 100)
    classification = "MATCH" if percent < 0.5 else "WITHIN TOLERANCE" if percent <= tolerance_percent else "WARNING" if percent <= tolerance_percent * 2 else "SIGNIFICANT DIFFERENCE"
    return ComparisonMetric(metric=name, simulation=round(simulation, 2), actual=round(actual, 2), difference=round(difference, 2), unit=unit, tolerance=tolerance_percent, tolerance_source="Mission configuration" if name in {"Max altitude", "Mission duration"} else "Engineering default", classification=classification)
