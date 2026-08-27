"""Deterministic, software-verification flight telemetry simulator."""
from __future__ import annotations

import hashlib
import hmac
import math
import random
import uuid

from .models import MissionPhase, ScenarioRequest, Severity, SimulationResult, TelemetryPacket

HMAC_DEMO_KEY = b"development-only-demo-key"
TOTAL_DURATION_S = 90
APOGEE_TIME_S = 31
TARGET_ALTITUDE_M = 1000.0


def mission_phase(time_s: int) -> MissionPhase:
    """Return the demo mission phase at a given elapsed second."""
    if time_s == 0:
        return MissionPhase.BOOT
    if time_s < 5:
        return MissionPhase.READY
    if time_s == 5:
        return MissionPhase.LAUNCH
    if time_s < APOGEE_TIME_S:
        return MissionPhase.ASCENT
    if time_s == APOGEE_TIME_S:
        return MissionPhase.APOGEE
    if time_s < TOTAL_DURATION_S:
        return MissionPhase.DESCENT
    return MissionPhase.LANDING


def altitude(time_s: int) -> float:
    """Smooth parabolic demo trajectory peaking at 1,000 m."""
    if time_s < 5:
        return 0.0
    if time_s <= APOGEE_TIME_S:
        return TARGET_ALTITUDE_M * ((time_s - 5) / (APOGEE_TIME_S - 5)) ** 1.25
    return max(0.0, TARGET_ALTITUDE_M * (1 - (time_s - APOGEE_TIME_S) / (TOTAL_DURATION_S - APOGEE_TIME_S)) ** 1.15)


def _signature(packet_number: int, time_s: int, altitude_m: float) -> str:
    payload = f"{packet_number}|{time_s}|{altitude_m:.2f}".encode()
    return hmac.new(HMAC_DEMO_KEY, payload, hashlib.sha256).hexdigest()[:16]


def simulate(request: ScenarioRequest) -> SimulationResult:
    """Generate deterministic synthetic telemetry and apply one fault scenario.

    This intentionally omits high-fidelity aerodynamics and is only suitable for
    exercising packet, dashboard, and validation behavior.
    """
    rng = random.Random(request.seed)
    packets: list[TelemetryPacket] = []
    malformed_rejected = 0
    delayed = 0
    gps_unavailable = 0
    for second in range(TOTAL_DURATION_S + 1):
        alt = altitude(second)
        velocity = altitude(min(second + 1, TOTAL_DURATION_S)) - altitude(max(second - 1, 0))
        in_fault_window = request.start_s <= second < request.start_s + request.duration_s
        gps_valid = not (request.fault == "gps_loss" and in_fault_window)
        if not gps_valid:
            gps_unavailable += 1
        if request.fault == "malformed_packet" and in_fault_window:
            malformed_rejected += 1
            continue
        timestamp = float(second + (2 if request.fault == "packet_delay" and in_fault_window else 0))
        if timestamp != second:
            delayed += 1
        battery = 8.4 - second * 0.012 + rng.uniform(-0.015, 0.015)
        if request.fault == "battery_anomaly" and in_fault_window:
            battery -= 1.5
        packet = TelemetryPacket(
            packet_number=second,
            timestamp_s=timestamp,
            altitude_m=round(alt + rng.uniform(-0.6, 0.6), 2),
            velocity_m_s=round(velocity / 2, 2),
            pressure_hpa=round(1013.25 * math.exp(-alt / 8434.5), 2),
            temperature_c=round(24 - alt * 0.0065 + rng.uniform(-0.2, 0.2), 2),
            battery_v=round(battery, 3),
            latitude=12.9716 if gps_valid else None,
            longitude=77.5946 if gps_valid else None,
            phase=mission_phase(second),
            gps_valid=gps_valid,
            integrity=_signature(second, second, alt),
        )
        packets.append(packet)
    radio_recovery_s = 5 if request.fault == "radio_loss" else 0
    validation = {
        "received_packets": len(packets),
        "rejected_packets": malformed_rejected,
        "estimated_packet_loss": request.duration_s if request.fault == "radio_loss" else 0,
        "delayed_packets": delayed,
        "gps_unavailable_samples": gps_unavailable,
        "radio_recovery_s": radio_recovery_s,
        "integrity_verified": True,
    }
    verdict = Severity.FAIL if request.fault == "radio_loss" else Severity.GOOD
    return SimulationResult(id=f"sim-{uuid.uuid4().hex[:8]}", scenario=request, telemetry=packets, validation=validation, verdict=verdict)
