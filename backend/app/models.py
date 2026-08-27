"""Typed domain models used by the validation services and API."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MissionPhase(str, Enum):
    BOOT = "BOOT"
    READY = "READY"
    LAUNCH = "LAUNCH"
    ASCENT = "ASCENT"
    APOGEE = "APOGEE"
    DESCENT = "DESCENT"
    LANDING = "LANDING"


class Severity(str, Enum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    FAIL = "FAIL"
    NOT_TESTED = "NOT TESTED"


class TelemetryPacket(BaseModel):
    """One validated mission telemetry sample."""

    packet_number: int = Field(ge=0)
    timestamp_s: float = Field(ge=0)
    altitude_m: float = Field(ge=-100, le=10000)
    velocity_m_s: float = Field(ge=-500, le=500)
    pressure_hpa: float = Field(ge=100, le=1200)
    temperature_c: float = Field(ge=-80, le=120)
    battery_v: float = Field(ge=0, le=20)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phase: MissionPhase
    gps_valid: bool = True
    integrity: str | None = None


class ScenarioRequest(BaseModel):
    """A deterministic scenario request for the software-only simulator."""

    name: str = "Normal mission"
    fault: str = "none"
    start_s: int = Field(default=40, ge=0, le=90)
    duration_s: int = Field(default=5, ge=1, le=60)
    seed: int = Field(default=2026, ge=0)

    @field_validator("fault")
    @classmethod
    def validate_fault(cls, value: str) -> str:
        allowed = {"none", "gps_loss", "radio_loss", "malformed_packet", "battery_anomaly", "packet_delay"}
        if value not in allowed:
            raise ValueError(f"fault must be one of: {', '.join(sorted(allowed))}")
        return value


class SimulationResult(BaseModel):
    """Reproducible synthetic simulation output."""

    id: str
    scenario: ScenarioRequest
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    configuration_version: str = "v1.7"
    software_version: str = "demo-a81f29"
    telemetry: list[TelemetryPacket]
    validation: dict[str, Any]
    verdict: Severity


class ComparisonMetric(BaseModel):
    metric: str
    simulation: float
    actual: float
    difference: float
    unit: str
    classification: str


class SecurityFinding(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    detail: str


class AuditEvent(BaseModel):
    action: str
    result: str
    detail: str
    actor: str = "local-user"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
