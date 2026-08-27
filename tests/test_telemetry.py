import unittest

from backend.app.telemetry import column_mapping, parse_csv


class TelemetryTests(unittest.TestCase):
    def test_alias_mapping(self):
        self.assertEqual(column_mapping(["alt", "temp", "volt"]), {"alt": "altitude_m", "temp": "temperature_c", "volt": "battery_v"})

    def test_valid_csv(self):
        data = "packet,time,alt,temp,volt,phase\n1,1,23,21,8.1,ASCENT\n"
        packets, errors, _ = parse_csv(data)
        self.assertEqual(len(packets), 1)
        self.assertFalse(errors)

    def test_missing_header(self):
        packets, errors, mapping = parse_csv("")
        self.assertFalse(packets)
        self.assertEqual(errors[0]["row"], 0)
        self.assertEqual(mapping, {})

    def test_invalid_temperature_is_rejected(self):
        packets, errors, _ = parse_csv("temp,phase\n500,READY\n")
        self.assertFalse(packets)
        self.assertEqual(errors[0]["row"], 2)

    def test_invalid_phase_is_rejected(self):
        packets, errors, _ = parse_csv("phase\nFLYING\n")
        self.assertFalse(packets)
        self.assertEqual(len(errors), 1)

    def test_optional_gps_is_allowed(self):
        packets, errors, _ = parse_csv("alt,phase\n2,READY\n")
        self.assertIsNone(packets[0].latitude)
        self.assertFalse(errors)

    def test_bad_numeric_is_rejected(self):
        packets, errors, _ = parse_csv("alt,phase\nnot-a-number,READY\n")
        self.assertFalse(packets)
        self.assertEqual(len(errors), 1)

    def test_multiple_rows_report_individual_errors(self):
        packets, errors, _ = parse_csv("alt,phase\n1,READY\n10001,ASCENT\n-200,DESCENT\n")
        self.assertEqual(len(packets), 1)
        self.assertEqual([error["row"] for error in errors], [3, 4])

    def test_alias_gps_mapping(self):
        mapping = column_mapping(["gps_lat", "gps_lon"])
        self.assertEqual(mapping["gps_lat"], "latitude")
        self.assertEqual(mapping["gps_lon"], "longitude")

    def test_packet_numbers_are_read(self):
        packets, _, _ = parse_csv("packet,time,phase\n9,7,READY\n")
        self.assertEqual(packets[0].packet_number, 9)
        self.assertEqual(packets[0].timestamp_s, 7)

