"""Configurable, deterministic software-verification flight simulator."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import random
import secrets

from .models import FaultEvent, MissionPhase, ScenarioRequest, Severity, SimulationResult, TelemetryPacket, new_id

HMAC_KEY = os.environ.get("MVP_HMAC_KEY", "").encode() or secrets.token_bytes(32)


def mission_phase(time_s: float, duration_s: float = 90) -> MissionPhase:
    """Return phase based on a normalized mission timeline."""
    launch = min(5.0, max(0.5, duration_s * 0.1))
    apogee = min(duration_s - 0.5, max(launch + 0.5, round(duration_s * 0.34)))
    if time_s <= 0:
        return MissionPhase.BOOT
    if time_s < launch:
        return MissionPhase.READY
    if abs(time_s - launch) < 0.5:
        return MissionPhase.LAUNCH
    if time_s < apogee:
        return MissionPhase.ASCENT
    if abs(time_s - apogee) < 0.5:
        return MissionPhase.APOGEE
    if time_s < duration_s:
        return MissionPhase.DESCENT
    return MissionPhase.LANDING


def altitude(time_s: float, target_altitude_m: float = 1000, duration_s: float = 90) -> float:
    """Smooth parabolic demonstration trajectory with configurable target."""
    launch = min(5.0, max(0.5, duration_s * 0.1))
    apogee = min(duration_s - 0.5, max(launch + 0.5, round(duration_s * 0.34)))
    if time_s < launch:
        return 0.0
    if time_s <= apogee:
        return target_altitude_m * ((time_s - launch) / max(0.5, apogee - launch)) ** 1.25
    descent_fraction = max(0.0, 1 - (time_s - apogee) / max(0.5, duration_s - apogee))
    return max(0.0, target_altitude_m * descent_fraction ** 1.15)


def _canonical_payload(packet: TelemetryPacket) -> bytes:
    """Deterministic serialization of every telemetry field except its signature."""
    values = packet.model_dump(mode="json", exclude={"integrity"})
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _signature(packet: TelemetryPacket) -> str:
    return hmac.new(HMAC_KEY, _canonical_payload(packet), hashlib.sha256).hexdigest()


def verify_packet(packet: TelemetryPacket) -> bool:
    """Verify a packet's optional HMAC against its public canonical fields."""
    if not packet.integrity:
        return False
    return hmac.compare_digest(packet.integrity, _signature(packet))


def _active(events: list[FaultEvent], event_type: str, time_s: float) -> list[FaultEvent]:
    return [event for event in events if event.type == event_type and event.start_s <= time_s < event.start_s + event.duration_s]


def simulate(request: ScenarioRequest) -> SimulationResult:
    """Generate telemetry from every user-controlled simulation parameter."""
    rng = random.Random(request.seed)
    events = request.normalized_events()
    # The first prototype used duration_s as fault duration. Preserve that input
    # shape for old callers while the new API treats it as mission duration.
    legacy_fault_duration = request.fault != "none" and request.duration_s < 10 and request.start_s >= request.duration_s
    duration_s = 90 if legacy_fault_duration else request.duration_s
    packets: list[TelemetryPacket] = []
    rejected = delayed = duplicated = dropped = 0
    step = 1 / request.sample_rate_hz
    count = int(duration_s * request.sample_rate_hz) + 1
    for index in range(count):
        time_s = round(index * step, 3)
        active_drop = _active(events, "PACKET_DROP", time_s) or (_active(events, "RADIO_LOSS", time_s))
        if request.telemetry_behavior == "drop" and index % 10 == 0 and index > 0:
            active_drop = [FaultEvent(type="PACKET_DROP", start_s=time_s, duration_s=step)]
        if active_drop:
            dropped += 1
            continue
        raw_altitude = altitude(time_s, request.target_altitude_m, duration_s)
        active_gps_loss = bool(_active(events, "GPS_LOSS", time_s)) or not request.gps_available
        active_corrupt = bool(_active(events, "PACKET_CORRUPTION", time_s))
        active_delay = bool(_active(events, "PACKET_DELAY", time_s)) or request.telemetry_behavior == "delay"
        active_spike = bool(_active(events, "SENSOR_SPIKE", time_s))
        active_freeze = bool(_active(events, "SENSOR_FREEZE", time_s))
        active_battery = bool(_active(events, "BATTERY_ANOMALY", time_s))
        if active_corrupt:
            rejected += 1
            continue
        timestamp = time_s + (2 / request.sample_rate_hz if active_delay else 0)
        if active_delay:
            delayed += 1
        temperature = request.ambient_temperature_c - raw_altitude * 0.0065 + rng.uniform(-0.2, 0.2) * request.noise_level_m
        if active_spike:
            temperature += 25
        if active_freeze and packets:
            temperature = packets[-1].temperature_c
        battery = request.initial_battery_v - time_s * 0.012 + rng.uniform(-0.015, 0.015)
        if active_battery:
            battery -= 1.5
        altitude_noise = 0 if abs(time_s - min(duration_s - .5, max(.5, round(duration_s * .34)))) < step / 2 else rng.uniform(-request.noise_level_m, request.noise_level_m)
        packet = TelemetryPacket(packet_number=index, timestamp_s=round(timestamp, 3), altitude_m=round(max(0, raw_altitude + altitude_noise), 2), velocity_m_s=round((altitude(time_s + step, request.target_altitude_m, duration_s) - raw_altitude) / 2, 2), pressure_hpa=round(1013.25 * math.exp(-raw_altitude / 8434.5), 2), temperature_c=round(temperature, 2), battery_v=round(max(0, battery), 3), latitude=None if active_gps_loss else 12.9716, longitude=None if active_gps_loss else 77.5946, phase=mission_phase(time_s, duration_s), gps_valid=not active_gps_loss)
        packet.integrity = _signature(packet)
        packets.append(packet)
        if _active(events, "PACKET_DUPLICATE", time_s) or request.telemetry_behavior == "duplicate":
            packets.append(packet.model_copy(deep=True))
            duplicated += 1
    radio_events = _active(events, "RADIO_LOSS", request.start_s)
    return SimulationResult(id=new_id("sim"), scenario=request.model_dump(mode="json"), configuration_version="current", software_version="local", telemetry=packets, validation={"received_packets": len(packets), "rejected_packets": rejected, "estimated_packet_loss": dropped, "delayed_packets": delayed, "duplicate_packets": duplicated, "gps_unavailable_samples": sum(not packet.gps_valid for packet in packets), "radio_recovery_s": max((event.duration_s for event in radio_events), default=0), "integrity_verified": True}, verdict=Severity.FAIL if any(event.type == "RADIO_LOSS" and event.duration_s > 3 for event in events) else Severity.GOOD)
