import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class EndToEndApiTests(unittest.TestCase):
    """Exercise the persisted API lifecycle against the real FastAPI app."""

    def test_create_simulate_import_compare_report(self):
        with TestClient(app) as client:
            created = client.post('/api/projects', json={"name": "API Integration", "vehicle_name": "Test Vehicle", "mission_name": "Test Mission", "target_altitude_m": 700, "telemetry_rate_hz": 1, "expected_duration_s": 30})
            self.assertEqual(created.status_code, 200)
            sim = client.post('/api/simulate', json={"name": "API run", "duration_s": 30, "target_altitude_m": 700, "seed": 12})
            self.assertEqual(sim.status_code, 200)
            simulation_id = sim.json()["id"]
            csv = "packet,time,alt,temp,volt,phase\n0,0,0,20,8,BOOT\n1,1,25,20,7.9,ASCENT\n2,2,50,20,7.8,APOGEE\n"
            preview = client.post('/api/telemetry/import', json={"name": "api.csv", "csv": csv})
            self.assertEqual(preview.json()["stage"], "mapping")
            stored = client.post('/api/telemetry/import', json={"name": "api.csv", "csv": csv, "confirm_mapping": True, "mapping": preview.json()["suggested_mapping"]})
            self.assertEqual(stored.json()["stage"], "stored")
            flight_id = stored.json()["flight"]["id"]
            compare = client.post('/api/compare', json={"simulation_id": simulation_id, "flight_id": flight_id})
            self.assertEqual(compare.status_code, 200)
            self.assertEqual(compare.json()["simulation_id"], simulation_id)
            report = client.post('/api/reports', json={"simulation_id": simulation_id, "flight_id": flight_id})
            self.assertEqual(report.status_code, 200)
            report_response = client.get(report.json()["url"])
            self.assertEqual(report_response.status_code, 200)
            self.assertIn("Mission Validation Report", report_response.text)

    def test_test_runner_and_security_are_persisted(self):
        with TestClient(app) as client:
            test = client.post('/api/tests', json={"name": "API GPS check", "expected_behavior": "GPS becomes invalid", "tolerance": 0, "scenario": {"name": "API GPS", "fault": "gps_loss", "start_s": 10, "duration_s": 20}})
            self.assertEqual(test.status_code, 200)
            run = client.post('/api/tests/run', json={})
            self.assertEqual(run.status_code, 200)
            finding = client.post('/api/security/scan', json={"name": "config.txt", "content": "token=\"abcdefghijklmnop\""})
            self.assertEqual(finding.status_code, 200)
            self.assertTrue(finding.json())
            self.assertTrue(any(event["action"] == "security_scan" for event in client.get('/api/audit').json()))
