"""Telemetry parsing and validation isolated from API and UI code."""
from __future__ import annotations

import csv
import io
from typing import Any

from pydantic import ValidationError

from .models import MissionPhase, TelemetryPacket

COLUMN_ALIASES = {"alt": "altitude_m", "altitude": "altitude_m", "temp": "temperature_c", "temperature": "temperature_c", "volt": "battery_v", "battery_voltage": "battery_v", "gps_lat": "latitude", "gps_lon": "longitude", "time": "timestamp_s", "packet": "packet_number"}


def column_mapping(headers: list[str]) -> dict[str, str]:
    """Return unambiguous common field aliases for an imported CSV header."""
    return {header: COLUMN_ALIASES[header.lower().strip()] for header in headers if header.lower().strip() in COLUMN_ALIASES}


def parse_csv(content: str) -> tuple[list[TelemetryPacket], list[dict[str, Any]], dict[str, str]]:
    """Safely parse CSV telemetry without modifying original upload content."""
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return [], [{"row": 0, "reason": "CSV header is missing"}], {}
    mapping = column_mapping(reader.fieldnames)
    packets: list[TelemetryPacket] = []
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(reader, start=2):
        normalized = {mapping.get(key, key): value for key, value in row.items()}
        try:
            packets.append(TelemetryPacket(
                packet_number=int(normalized.get("packet_number", index - 2)),
                timestamp_s=float(normalized.get("timestamp_s", index - 2)),
                altitude_m=float(normalized.get("altitude_m", 0)),
                velocity_m_s=float(normalized.get("velocity_m_s", 0)),
                pressure_hpa=float(normalized.get("pressure_hpa", 1013.25)),
                temperature_c=float(normalized.get("temperature_c", 20)),
                battery_v=float(normalized.get("battery_v", 8.0)),
                latitude=float(normalized["latitude"]) if normalized.get("latitude") else None,
                longitude=float(normalized["longitude"]) if normalized.get("longitude") else None,
                phase=MissionPhase(normalized.get("phase", "READY")),
                gps_valid=str(normalized.get("gps_valid", "true")).lower() == "true",
            ))
        except (ValueError, ValidationError) as exc:
            errors.append({"row": index, "reason": str(exc).splitlines()[0]})
    return packets, errors, mapping
