import unittest
import base64
import base64

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
            report_json = client.get(report.json()["json_url"])
            self.assertEqual(report_json.status_code, 200)
            self.assertEqual(report_json.json()["project"]["name"], "API Integration")

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

    def test_workspace_artifact_investigation_and_portable_archive(self):
        with TestClient(app) as client:
            created = client.post('/api/projects', json={"name": "Archive workflow", "vehicle_name": "Blank vehicle", "mission_name": "Artifact mission", "target_altitude_m": 600, "telemetry_rate_hz": 1, "expected_duration_s": 25}).json()
            artifact = client.post('/api/artifacts/import', json={"name": "vehicle.ork", "content": "<openrocket><rocket name='Imported Rocket'><bodytube><name>Airframe</name><length>1.2</length><radius>0.04</radius><mass>0.8</mass></bodytube></rocket></openrocket>"})
            self.assertEqual(artifact.status_code, 200)
            self.assertTrue(artifact.json()["normalized_vehicle"]["vehicle_updated"])
            self.assertEqual(client.get('/api/vehicle').json()["name"], "Imported Rocket")
            sim = client.post('/api/simulate', json={"name": "Archive run", "duration_s": 25, "target_altitude_m": 600, "seed": 4}).json()
            imported = client.post('/api/telemetry/import', json={"name": "archive.csv", "csv": "packet,time,alt,temp,volt,phase\n0,0,0,20,8,BOOT\n1,1,20,19,7.9,ASCENT\n"}).json()
            flight = client.post('/api/telemetry/import', json={"name": "archive.csv", "csv": "packet,time,alt,temp,volt,phase\n0,0,0,20,8,BOOT\n1,1,20,19,7.9,ASCENT\n", "confirm_mapping": True, "mapping": imported["suggested_mapping"]}).json()["flight"]
            investigation = client.post('/api/investigations', json={"observation": "Imported flight is below simulation", "possible_causes": ["mass"], "simulation_id": sim["id"], "flight_id": flight["id"]})
            self.assertEqual(investigation.status_code, 200)
            self.assertEqual(client.patch(f"/api/investigations/{investigation.json()['id']}", json={"status": "UNDER INVESTIGATION"}).json()["status"], "UNDER INVESTIGATION")
            exported = client.get(f"/api/projects/{created['id']}/export")
            self.assertEqual(exported.status_code, 200)
            restored = client.post('/api/projects/import', json={"archive_base64": base64.b64encode(exported.content).decode()})
            self.assertEqual(restored.status_code, 200)
            self.assertIn("(imported)", restored.json()["name"])
            self.assertTrue(client.get('/api/artifacts').json())

    def test_workspace_artifact_investigation_and_archive_round_trip(self):
        with TestClient(app) as client:
            project = client.post('/api/projects', json={"name": "Archive Integration", "vehicle_name": "Blank Vehicle", "mission_name": "Archive Mission", "target_altitude_m": 600, "telemetry_rate_hz": 2, "expected_duration_s": 25}).json()
            ork = "<openrocket><rocket name='Imported Vehicle'><subcomponents><bodytube><name>Main body</name><length>1.2</length><radius>0.04</radius><mass>0.8</mass></bodytube><nosecone><length>0.3</length><radius>0.04</radius></nosecone></subcomponents></rocket></openrocket>"
            imported = client.post('/api/artifacts/import', json={"name": "vehicle.ork", "content": ork})
            self.assertEqual(imported.status_code, 200)
            self.assertTrue(imported.json()["normalized_vehicle"]["vehicle_updated"])
            self.assertEqual(client.get('/api/vehicle').json()["name"], "Imported Vehicle")
            artifact = imported.json()["artifact"]
            self.assertEqual(client.get(f"/api/artifacts/{artifact['id']}/download").content, ork.encode())

            sim = client.post('/api/simulate', json={"name": "Archive sim", "duration_s": 25, "target_altitude_m": 600, "seed": 5}).json()
            csv = "packet,time,alt,temp,volt,phase\n0,0,0,20,8,BOOT\n1,1,20,19,7.9,ASCENT\n"
            mapping = client.post('/api/telemetry/import', json={"name": "archive.csv", "csv": csv}).json()["suggested_mapping"]
            flight = client.post('/api/telemetry/import', json={"name": "archive.csv", "csv": csv, "confirm_mapping": True, "mapping": mapping}).json()["flight"]
            investigation = client.post('/api/investigations', json={"observation": "Verify imported profile against simplified model", "possible_causes": ["sensor calibration"], "simulation_id": sim["id"], "flight_id": flight["id"]})
            self.assertEqual(investigation.status_code, 200)
            resolved = client.patch(f"/api/investigations/{investigation.json()['id']}", json={"status": "UNDER INVESTIGATION"})
            self.assertEqual(resolved.json()["status"], "UNDER INVESTIGATION")

            archive = client.get(f"/api/projects/{project['id']}/export")
            self.assertEqual(archive.status_code, 200)
            reopened = client.post('/api/projects/import', json={"archive_base64": base64.b64encode(archive.content).decode()})
            self.assertEqual(reopened.status_code, 200)
            self.assertTrue(reopened.json()["name"].endswith("(imported)"))
            self.assertTrue(client.get('/api/artifacts').json())
