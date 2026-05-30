import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - depends on optional API dependencies
    TestClient = None

from network_ai_mvp.api import create_app
from network_ai_mvp.executor import CommandResult


class FakeExecutor:
    def __init__(self, *, returncode: int = 0, stderr: str = "", error: Exception | None = None) -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.error = error
        self.calls = []

    def run(self, plan, *, credential_path):
        self.calls.append((plan, credential_path))
        if self.error:
            raise self.error
        return CommandResult(
            device_id=plan.device.device_id,
            hostname=plan.device.hostname,
            management_ip=plan.device.management_ip,
            purpose=plan.purpose,
            commands=plan.commands,
            stdout="collected output",
            stderr=self.stderr,
            returncode=self.returncode,
        )


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.audit_path = Path(self.temp_dir.name) / "audit.jsonl"
        self.executor = FakeExecutor()
        app = create_app(
            audit_log_path=self.audit_path,
            executor=self.executor,
            credential_resolver=lambda credential_ref: Path(self.temp_dir.name) / f"{credential_ref}.xml",
        )
        self.client = TestClient(app)

    def test_health_and_devices_endpoints(self) -> None:
        health = self.client.get("/health")
        index = self.client.get("/")
        monitoring = self.client.get("/monitoring")
        devices = self.client.get("/devices")
        device = self.client.get("/devices/arista-10g-core")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok", "mode": "read-only"})
        self.assertEqual(index.status_code, 200)
        self.assertIn("Network AI MVP", index.text)
        self.assertEqual(monitoring.status_code, 200)
        self.assertIn("Monitoring", monitoring.text)
        self.assertEqual(devices.status_code, 200)
        self.assertGreaterEqual(len(devices.json()), 2)
        self.assertNotIn("credential_ref", devices.json()[0])
        self.assertNotIn("credential_ref", devices.text)
        self.assertEqual(device.status_code, 200)
        self.assertEqual(device.json()["management_ip"], "172.17.17.2")
        self.assertNotIn("credential_ref", device.json())
        self.assertNotIn("credential_ref", device.text)

    def test_command_plan_endpoint(self) -> None:
        response = self.client.get("/devices/arista-10g-core/command-plan/topology")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["purpose"], "topology")
        self.assertIn("show lldp neighbors", payload["commands"])
        self.assertTrue(payload["read_only"])
        self.assertNotIn("credential_ref", payload["device"])
        self.assertNotIn("credential_ref", response.text)

    def test_device_diagnostics_endpoint(self) -> None:
        response = self.client.get("/devices/arista-2f-outpatient/diagnostics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["device_id"], "arista-2f-outpatient")
        titles = {finding["title"] for finding in payload["findings"]}
        self.assertIn("Disabled historical high-error port", titles)
        self.assertIn("[CRITICAL]", payload["summary"])
        self.assertIn("Not live truth", payload["summary"])

    def test_device_neighbors_endpoint_returns_reference_neighbors(self) -> None:
        response = self.client.get("/devices/cisco-backbone/neighbors")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["device_id"], "cisco-backbone")
        names = {neighbor["neighbor_name"] for neighbor in payload["neighbors"]}
        self.assertIn("9F_BB_ARI_17.2", names)
        self.assertIn("9F Computer Room Cisco Switch", names)
        computer_room = [
            neighbor
            for neighbor in payload["neighbors"]
            if neighbor["neighbor_name"] == "9F Computer Room Cisco Switch"
        ][0]
        self.assertIsNone(computer_room["management_ip"])
        self.assertEqual(computer_room["status"], "ip-not-set")

    def test_collect_uses_mocked_executor_and_writes_audit_metadata(self) -> None:
        response = self.client.post("/devices/arista-10g-core/collect/baseline")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["device_id"], "arista-10g-core")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["returncode"], 0)
        self.assertIn("stdout_bytes", payload)
        self.assertEqual(payload["stdout"], "collected output")
        self.assertEqual(len(self.executor.calls), 1)

        audit_record = json.loads(self.audit_path.read_text(encoding="utf-8"))
        self.assertEqual(audit_record["device_id"], "arista-10g-core")
        self.assertEqual(audit_record["success"], True)
        self.assertNotIn("password", self.audit_path.read_text(encoding="utf-8").lower())

    def test_collect_blocks_unknown_purpose_before_executor(self) -> None:
        response = self.client.post("/devices/arista-10g-core/collect/shutdown")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.executor.calls, [])
        audit_record = json.loads(self.audit_path.read_text(encoding="utf-8"))
        self.assertEqual(audit_record["success"], False)
        self.assertEqual(audit_record["commands"], [])

    def test_audit_log_endpoint_returns_redacted_events(self) -> None:
        self.audit_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-29T00:00:00Z",
                    "device_id": "arista-10g-core",
                    "management_ip": "172.17.17.2",
                    "purpose": "baseline",
                    "commands": ["show version"],
                    "success": False,
                    "returncode": None,
                    "error_summary": "password=redact-me credential_ref arista_kcl C:\\Users\\SPW\\arista_kcl.cred.xml",
                    "credential_ref": "arista_kcl",
                }
            ),
            encoding="utf-8",
        )

        response = self.client.get("/audit-log")

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertNotIn("redact-me", text)
        self.assertNotIn("arista_kcl", text)
        self.assertNotIn(".cred.xml", text)
        self.assertNotIn("credential_ref", text)
        self.assertEqual(response.json()["events"][0]["device_id"], "arista-10g-core")

    def test_collect_error_detail_is_redacted(self) -> None:
        executor = FakeExecutor(
            error=RuntimeError(
                "failed credential_ref arista_kcl with password=redact-me "
                "NETWORK_AI_CREDENTIAL_ARISTA_KCL C:\\Users\\SPW\\arista_kcl.cred.xml"
            )
        )
        app = create_app(
            audit_log_path=self.audit_path,
            executor=executor,
            credential_resolver=lambda credential_ref: Path(self.temp_dir.name) / f"{credential_ref}.xml",
        )
        client = TestClient(app)

        response = client.post("/devices/arista-10g-core/collect/baseline")

        self.assertEqual(response.status_code, 500)
        text = response.text
        self.assertNotIn("arista_kcl", text)
        self.assertNotIn("redact-me", text)
        self.assertNotIn(".cred.xml", text)
        self.assertNotIn("NETWORK_AI_CREDENTIAL_ARISTA_KCL", text)
        self.assertNotIn("credential_ref", text)
        self.assertNotIn("password", text.lower())

    def test_collect_failure_summarizes_powershell_clixml_error(self) -> None:
        executor = FakeExecutor(
            returncode=1,
            stderr=(
                '#< CLIXML\n<Objs><S S="Error">Login failed._x000D__x000A_</S>'
                '<S S="Error">at script line 152_x000D__x000A_</S></Objs>'
            ),
        )
        app = create_app(
            audit_log_path=self.audit_path,
            executor=executor,
            credential_resolver=lambda credential_ref: Path(self.temp_dir.name) / f"{credential_ref}.xml",
        )
        client = TestClient(app)

        response = client.post("/devices/arista-10g-core/collect/baseline")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_summary"], "Login failed.")
        self.assertIn("Login failed.", payload["stderr"])
        self.assertNotIn("#< CLIXML", payload["stderr"])


if __name__ == "__main__":
    unittest.main()
