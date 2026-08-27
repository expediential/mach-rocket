"""Typed domain models for persisted projects, telemetry, scenarios, and tests."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


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


class EntityTimestamps(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetryPacket(BaseModel):
    """One bounded and validated telemetry sample."""

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


class FaultEvent(BaseModel):
    """A fault event placed on a scenario timeline."""

    type: str
    start_s: float = Field(ge=0)
    duration_s: float = Field(default=5, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

    @field_validator("type")
    @classmethod
    def type_is_known(cls, value: str) -> str:
        allowed = {"GPS_LOSS", "RADIO_LOSS", "PACKET_DROP", "PACKET_DUPLICATE", "PACKET_DELAY", "PACKET_CORRUPTION", "SENSOR_SPIKE", "SENSOR_FREEZE", "BATTERY_ANOMALY", "SOFTWARE_RESTART"}
        if value not in allowed:
            raise ValueError(f"event type must be one of: {', '.join(sorted(allowed))}")
        return value


class ScenarioRequest(BaseModel):
    """User-controlled simulation inputs and a composable fault timeline."""

    name: str = "Normal mission"
    duration_s: int = Field(default=90, ge=1, le=3600)
    sample_rate_hz: float = Field(default=1, gt=0, le=20)
    target_altitude_m: float = Field(default=1000, gt=0, le=10000)
    initial_battery_v: float = Field(default=8.4, ge=0, le=20)
    ambient_temperature_c: float = Field(default=24, ge=-80, le=80)
    noise_level_m: float = Field(default=0.6, ge=0, le=100)
    gps_available: bool = True
    telemetry_behavior: Literal["normal", "drop", "duplicate", "delay"] = "normal"
    seed: int = Field(default=2026, ge=0)
    events: list[FaultEvent] = Field(default_factory=list)
    # Backwards-compatible one-fault form used by the first prototype client.
    fault: str = "none"
    start_s: int = Field(default=40, ge=0, le=3600)

    @field_validator("fault")
    @classmethod
    def fault_is_known(cls, value: str) -> str:
        allowed = {"none", "gps_loss", "radio_loss", "malformed_packet", "battery_anomaly", "packet_delay", "packet_drop", "packet_duplicate"}
        if value not in allowed:
            raise ValueError(f"fault must be one of: {', '.join(sorted(allowed))}")
        return value

    def normalized_events(self) -> list[FaultEvent]:
        """Return explicit events plus the legacy one-fault value if supplied."""
        if self.events or self.fault == "none":
            return self.events
        event_type = {"gps_loss": "GPS_LOSS", "radio_loss": "RADIO_LOSS", "malformed_packet": "PACKET_CORRUPTION", "battery_anomaly": "BATTERY_ANOMALY", "packet_delay": "PACKET_DELAY", "packet_drop": "PACKET_DROP", "packet_duplicate": "PACKET_DUPLICATE"}[self.fault]
        return [FaultEvent(type=event_type, start_s=self.start_s, duration_s=self.duration_s if self.duration_s < 10 else 5)]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    vehicle_name: str = Field(min_length=1, max_length=120)
    mission_name: str = Field(min_length=1, max_length=160)
    target_altitude_m: float = Field(gt=0, le=10000)
    telemetry_rate_hz: float = Field(gt=0, le=20)
    expected_duration_s: int = Field(gt=0, le=3600)


class ConfigurationUpdate(BaseModel):
    target_altitude_m: float = Field(gt=0, le=10000)
    telemetry_rate_hz: float = Field(gt=0, le=20)
    expected_duration_s: int = Field(gt=0, le=3600)
    reason: str = Field(default="Mission configuration updated", max_length=240)


class CsvImport(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    csv: str = Field(max_length=5_000_000)
    confirm_mapping: bool = False
    mapping: dict[str, str] | None = None


class CompareRequest(BaseModel):
    simulation_id: str
    flight_id: str


class TestCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    scenario: ScenarioRequest
    expected_behavior: str = Field(min_length=1, max_length=500)
    tolerance: float = Field(default=0, ge=0, le=100)


class ScanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    content: str = Field(max_length=200_000)


class AuditEvent(BaseModel):
    action: str
    result: str
    detail: str
    object_id: str | None = None
    actor: str = "local-user"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComparisonMetric(BaseModel):
    metric: str
    simulation: float
    actual: float
    difference: float
    unit: str
    tolerance: float
    tolerance_source: str
    classification: str


class SecurityFinding(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationResult(BaseModel):
    """Persistable simulation output with complete telemetry."""

    id: str
    scenario: dict[str, Any]
    configuration_version: str
    software_version: str
    telemetry: list[TelemetryPacket]
    validation: dict[str, Any]
    verdict: Severity
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
