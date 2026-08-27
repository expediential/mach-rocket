"""Telemetry parsing, schema validation, and integrity helpers."""
from __future__ import annotations

import csv
import io
from typing import Any

from pydantic import ValidationError

from .models import MissionPhase, TelemetryPacket

COLUMN_ALIASES = {"alt": "altitude_m", "altitude": "altitude_m", "altitude_m": "altitude_m", "temp": "temperature_c", "temperature": "temperature_c", "temperature_c": "temperature_c", "volt": "battery_v", "voltage": "battery_v", "battery_voltage": "battery_v", "battery_v": "battery_v", "gps_lat": "latitude", "lat": "latitude", "gps_lon": "longitude", "lon": "longitude", "time": "timestamp_s", "time_sec": "timestamp_s", "timestamp": "timestamp_s", "timestamp_s": "timestamp_s", "packet": "packet_number", "packet_no": "packet_number", "packet_number": "packet_number", "vel": "velocity_m_s", "velocity": "velocity_m_s", "pressure": "pressure_hpa", "phase": "phase", "gps_valid": "gps_valid"}


def column_mapping(headers: list[str]) -> dict[str, str]:
    """Return only unambiguous known aliases; unknown columns are left untouched."""
    return {header: COLUMN_ALIASES[header.lower().strip()] for header in headers if header.lower().strip() in COLUMN_ALIASES}


def _bool(value: Any) -> bool:
    return str(value).strip().lower() not in {"false", "0", "no", "invalid", "none"}


def parse_csv(content: str, mapping_override: dict[str, str] | None = None) -> tuple[list[TelemetryPacket], list[dict[str, Any]], dict[str, str]]:
    """Parse CSV telemetry without changing source bytes or executing content."""
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return [], [{"row": 0, "reason": "CSV header is missing"}], {}
    mapping = mapping_override or column_mapping(reader.fieldnames)
    packets: list[TelemetryPacket] = []
    errors: list[dict[str, Any]] = []
    previous_packet = -1
    for index, row in enumerate(reader, start=2):
        normalized = {mapping.get(key, key): value for key, value in row.items()}
        try:
            packet_number = int(normalized.get("packet_number", index - 2))
            if packet_number == previous_packet:
                errors.append({"row": index, "reason": "duplicate packet number"})
                continue
            if packet_number < previous_packet:
                errors.append({"row": index, "reason": "packet numbers are out of order"})
                continue
            packet = TelemetryPacket(packet_number=packet_number, timestamp_s=float(normalized.get("timestamp_s", index - 2)), altitude_m=float(normalized.get("altitude_m", 0)), velocity_m_s=float(normalized.get("velocity_m_s", 0)), pressure_hpa=float(normalized.get("pressure_hpa", 1013.25)), temperature_c=float(normalized.get("temperature_c", 20)), battery_v=float(normalized.get("battery_v", 8.0)), latitude=float(normalized["latitude"]) if normalized.get("latitude") else None, longitude=float(normalized["longitude"]) if normalized.get("longitude") else None, phase=MissionPhase(normalized.get("phase", "READY")), gps_valid=_bool(normalized.get("gps_valid", "true")))
            packets.append(packet)
            previous_packet = packet_number
        except (ValueError, ValidationError) as exc:
            errors.append({"row": index, "reason": str(exc).splitlines()[0]})
    return packets, errors, mapping


def telemetry_stats(packets: list[TelemetryPacket]) -> dict[str, Any]:
    """Compute reusable flight statistics from validated packets."""
    if not packets:
        return {"packets": 0, "duration_s": 0, "max_altitude_m": 0, "max_velocity_m_s": 0, "packet_loss": 0, "gps_invalid": 0}
    numbers = [packet.packet_number for packet in packets]
    return {"packets": len(packets), "duration_s": round(packets[-1].timestamp_s - packets[0].timestamp_s, 3), "max_altitude_m": round(max(packet.altitude_m for packet in packets), 2), "max_velocity_m_s": round(max(abs(packet.velocity_m_s) for packet in packets), 2), "packet_loss": max(0, max(numbers) - min(numbers) + 1 - len(set(numbers))), "gps_invalid": sum(not packet.gps_valid for packet in packets)}
