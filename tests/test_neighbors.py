import json
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.neighbors import get_neighbors_for_device, load_backbone_neighbors


class NeighborTests(unittest.TestCase):
    def test_load_seed_backbone_neighbors(self) -> None:
        path = Path(__file__).resolve().parents[1] / "inventory" / "backbone_neighbors.json"

        neighbors = get_neighbors_for_device(path, "cisco-backbone")

        self.assertGreaterEqual(len(neighbors), 2)
        self.assertTrue(any(item.neighbor_name == "9F_BB_ARI_17.2" for item in neighbors))
        ip_not_set = [item for item in neighbors if item.status == "ip-not-set"]
        self.assertEqual(ip_not_set[0].management_ip, None)

    def test_missing_reference_file_returns_empty_list(self) -> None:
        neighbors = load_backbone_neighbors("missing-neighbors.json")

        self.assertEqual(neighbors, [])

    def test_invalid_reference_shape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "neighbors.json"
            path.write_text(json.dumps({"bad": "shape"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_backbone_neighbors(path)


if __name__ == "__main__":
    unittest.main()
