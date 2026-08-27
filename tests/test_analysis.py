import unittest

from backend.app.comparison import compare
from backend.app.models import MissionPhase, ScenarioRequest, TelemetryPacket
from backend.app.ork import parse_ork
from backend.app.security import scan_text
from backend.app.simulator import simulate


def packet(altitude_m: float, timestamp_s: float = 0, temperature_c: float = 20) -> TelemetryPacket:
    return TelemetryPacket(packet_number=int(timestamp_s), timestamp_s=timestamp_s, altitude_m=altitude_m, velocity_m_s=0, pressure_hpa=1000, temperature_c=temperature_c, battery_v=8, phase=MissionPhase.ASCENT)


class ComparisonTests(unittest.TestCase):
    def test_identical_flights_match(self):
        flight = [packet(0), packet(1000, 31)]
        result = compare(flight, flight)
        self.assertEqual(result["metrics"][0].classification, "MATCH")

    def test_altitude_difference_is_warning_or_significant(self):
        result = compare([packet(0), packet(1000, 31)], [packet(0), packet(850, 31)])
        self.assertEqual(result["metrics"][0].classification, "SIGNIFICANT DIFFERENCE")

    def test_apogee_time_comparison(self):
        result = compare([packet(0), packet(1000, 31)], [packet(0), packet(1000, 30)])
        self.assertEqual(result["metrics"][1].difference, -1)

    def test_investigation_language_is_cautious(self):
        result = compare(simulate(ScenarioRequest()).telemetry, simulate(ScenarioRequest()).telemetry)
        self.assertIn("not asserted root causes", result["note"])

    def test_packet_count_comparison(self):
        result = compare([packet(0), packet(10)], [packet(0)])
        self.assertEqual(result["metrics"][3].difference, -1)

    def test_temperature_metric_is_present(self):
        result = compare([packet(0), packet(100, 1, 15)], [packet(0), packet(100, 1, 20)])
        self.assertEqual(result["metrics"][2].difference, 2.5)


class OrkTests(unittest.TestCase):
    def test_extracts_rocket_name(self):
        self.assertEqual(parse_ork('<openrocket><rocket name="Falcon"/></openrocket>')["rocket_name"], "Falcon")

    def test_counts_stages(self):
        self.assertEqual(parse_ork("<openrocket><stage/><axialstage/></openrocket>")["stages"], 2)

    def test_collects_optional_fields(self):
        result = parse_ork("<openrocket><rocket name='F'/><mass>1.8</mass><length>1.3</length><motor>A8</motor></openrocket>")
        self.assertEqual(result["mass_kg"], "1.8")
        self.assertEqual(result["length_m"], "1.3")
        self.assertEqual(result["motor"], "A8")

    def test_malformed_xml_becomes_warning(self):
        result = parse_ork("<rocket>")
        self.assertTrue(result["warnings"])
        self.assertIsNone(result["rocket_name"])

    def test_missing_name_does_not_fail(self):
        result = parse_ork("<openrocket><stage/></openrocket>")
        self.assertTrue(result["warnings"])

    def test_namespace_is_tolerated(self):
        result = parse_ork('<o xmlns="x"><rocket name="F"/></o>')
        self.assertEqual(result["rocket_name"], "F")


class SecurityTests(unittest.TestCase):
    def test_private_key_is_detected(self):
        findings = scan_text("key.pem", "-----BEGIN PRIVATE KEY-----")
        self.assertEqual(findings[0].severity, "HIGH")

    def test_token_is_detected(self):
        findings = scan_text("config.py", 'api_key="abcDEFGH123456789"')
        self.assertTrue(findings)

    def test_benign_text_is_not_finding(self):
        self.assertFalse(scan_text("notes.txt", "Altitude target: 1000 m"))

    def test_finding_sanitizes_path(self):
        finding = scan_text("../../secrets.txt", 'token="abcdefghijklmnop"')[0]
        self.assertIn("secrets.txt", finding.detail)
        self.assertNotIn("../", finding.detail)

    def test_multiple_patterns_can_be_found(self):
        findings = scan_text("a.txt", 'token="abcdefghijklmnop"\n-----BEGIN PRIVATE KEY-----')
        self.assertEqual(len(findings), 2)

    def test_detection_is_case_insensitive(self):
        self.assertTrue(scan_text("config.txt", 'PASSWORD="abcdefghijklmnop"'))
