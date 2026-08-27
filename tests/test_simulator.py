import unittest

from backend.app.models import MissionPhase, ScenarioRequest, Severity
from backend.app.simulator import altitude, mission_phase, simulate, verify_packet


class SimulatorTests(unittest.TestCase):
    def test_normal_flight_has_full_telemetry(self):
        result = simulate(ScenarioRequest())
        self.assertEqual(len(result.telemetry), 91)
        self.assertEqual(result.verdict, Severity.GOOD)

    def test_normal_flight_reaches_target(self):
        self.assertAlmostEqual(max(packet.altitude_m for packet in simulate(ScenarioRequest()).telemetry), 1000, delta=1)

    def test_seed_is_reproducible(self):
        one = simulate(ScenarioRequest(seed=9))
        two = simulate(ScenarioRequest(seed=9))
        self.assertEqual(one.telemetry[25].altitude_m, two.telemetry[25].altitude_m)

    def test_gps_loss_marks_gps_invalid(self):
        result = simulate(ScenarioRequest(fault="gps_loss", start_s=40, duration_s=5))
        self.assertEqual(sum(not packet.gps_valid for packet in result.telemetry), 5)

    def test_malformed_packets_are_rejected(self):
        result = simulate(ScenarioRequest(fault="malformed_packet", start_s=40, duration_s=5))
        self.assertEqual(result.validation["rejected_packets"], 5)
        self.assertEqual(len(result.telemetry), 86)

    def test_radio_fault_fails_recovery_requirement(self):
        result = simulate(ScenarioRequest(fault="radio_loss"))
        self.assertEqual(result.verdict, Severity.FAIL)
        self.assertEqual(result.validation["radio_recovery_s"], 5)

    def test_packet_delay_is_recorded(self):
        result = simulate(ScenarioRequest(fault="packet_delay", duration_s=4))
        self.assertEqual(result.validation["delayed_packets"], 4)

    def test_battery_fault_changes_voltage(self):
        normal = simulate(ScenarioRequest(seed=7)).telemetry[40].battery_v
        failed = simulate(ScenarioRequest(seed=7, fault="battery_anomaly")).telemetry[40].battery_v
        self.assertGreater(normal - failed, 1.4)

    def test_phase_sequence(self):
        self.assertEqual(mission_phase(0), MissionPhase.BOOT)
        self.assertEqual(mission_phase(5), MissionPhase.LAUNCH)
        self.assertEqual(mission_phase(31), MissionPhase.APOGEE)
        self.assertEqual(mission_phase(90), MissionPhase.LANDING)

    def test_trajectory_does_not_go_negative(self):
        self.assertTrue(all(altitude(second) >= 0 for second in range(91)))

    def test_scenario_rejects_unknown_fault(self):
        with self.assertRaises(ValueError):
            ScenarioRequest(fault="detonate")

    def test_integrity_signature_present(self):
        self.assertEqual(len(simulate(ScenarioRequest()).telemetry[0].integrity), 16)

    def test_integrity_detects_tampering(self):
        packet = simulate(ScenarioRequest()).telemetry[0]
        self.assertTrue(verify_packet(packet))
        packet.altitude_m += 1
        self.assertFalse(verify_packet(packet))
