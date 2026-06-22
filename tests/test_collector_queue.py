import unittest
from time import sleep

from network_ai_mvp.collector import CollectionQueue, CommandResult
from network_ai_mvp.inventory import load_devices
from network_ai_mvp.policy import build_command_plan


class QueueAdapter:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error

    def supports(self, device) -> bool:
        return True

    def collect(self, device, plans, *, credential_path):
        if self.error:
            raise self.error
        return (
            CommandResult(
                device_id=device.device_id,
                hostname=device.hostname,
                management_ip=device.management_ip,
                purpose="check",
                commands=tuple(command for plan in plans for command in plan.commands),
                stdout="queued output",
                stderr="",
                returncode=0,
            ),
        )


class CollectorQueueTests(unittest.TestCase):
    def test_queue_runs_collection_job_in_worker(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plans = [build_command_plan(device, "baseline")]
        queue = CollectionQueue(max_workers=1)
        self.addCleanup(queue.shutdown)

        submitted = queue.submit(
            adapter=QueueAdapter(),
            device=device,
            plans=plans,
            credential_path="credential.xml",
        )

        self.assertEqual(submitted.status, "queued")
        snapshot = None
        for _ in range(100):
            snapshot = queue.get(submitted.job_id)
            if snapshot and snapshot.status == "succeeded":
                break
            sleep(0.01)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.status, "succeeded")
        self.assertEqual(snapshot.results[0].stdout, "queued output")

    def test_queue_records_adapter_failure(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plans = [build_command_plan(device, "baseline")]
        queue = CollectionQueue(max_workers=1)
        self.addCleanup(queue.shutdown)

        submitted = queue.submit(
            adapter=QueueAdapter(error=RuntimeError("adapter failed")),
            device=device,
            plans=plans,
            credential_path="credential.xml",
        )

        snapshot = None
        for _ in range(100):
            snapshot = queue.get(submitted.job_id)
            if snapshot and snapshot.status == "failed":
                break
            sleep(0.01)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.status, "failed")
        self.assertIn("adapter failed", snapshot.error)


if __name__ == "__main__":
    unittest.main()
