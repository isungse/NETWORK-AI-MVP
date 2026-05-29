import json
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.audit import append_audit_event, new_audit_event, read_audit_events, redact_text, redact_value


class AuditTests(unittest.TestCase):
    def test_audit_log_redacts_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.jsonl"
            sensitive_value = "redact-me"
            event = new_audit_event(
                device_id="arista-10g-core",
                hostname="9F_BB_ARI_17.2",
                management_ip="172.17.17.2",
                purpose="baseline",
                commands=("show version",),
                success=False,
                returncode=1,
                error_summary=(
                    f"login failed password={sensitive_value} "
                    "credential_ref arista_kcl C:\\Users\\SPW\\arista_kcl.cred.xml"
                ),
            )

            append_audit_event(audit_path, event)

            contents = audit_path.read_text(encoding="utf-8")
            self.assertNotIn(sensitive_value, contents)
            self.assertNotIn("arista_kcl", contents)
            self.assertNotIn(".cred.xml", contents)
            self.assertNotIn("credential_ref", contents)
            record = json.loads(contents)
            self.assertEqual(record["device_id"], "arista-10g-core")
            self.assertEqual(record["commands"], ["show version"])

    def test_read_audit_events_returns_redacted_recent_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.jsonl"
            audit_path.write_text(
                "\n".join(
                    [
                        json.dumps({"device_id": "old", "password": "redact-me"}),
                        json.dumps({"device_id": "new", "commands": ["show version"]}),
                    ]
                ),
                encoding="utf-8",
            )

            records = read_audit_events(audit_path, limit=1)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["device_id"], "new")

    def test_redacts_secret_field_names(self) -> None:
        sensitive_value = "redact-me"
        value = redact_value(
            {
                "password": sensitive_value,
                "credential_ref": "arista_kcl",
                "nested": {"token": sensitive_value},
            }
        )

        self.assertNotIn("password", value)
        self.assertNotIn("credential_ref", value)
        self.assertNotIn("token", value["nested"])

    def test_redacts_credential_identifiers_in_text(self) -> None:
        value = redact_text(
            "credential_ref 'arista_kcl' uses NETWORK_AI_CREDENTIAL_ARISTA_KCL "
            "and C:\\Users\\SPW\\arista_kcl.cred.xml"
        )

        self.assertNotIn("arista_kcl", value)
        self.assertNotIn("NETWORK_AI_CREDENTIAL_ARISTA_KCL", value)
        self.assertNotIn(".cred.xml", value)
        self.assertNotIn("credential_ref", value)


if __name__ == "__main__":
    unittest.main()
