"""Mechanical tests only; no synthetic polygon is treated as field truth."""

import tempfile
import unittest
from pathlib import Path

from spring_agents.orchestrator import assess
from spring_agents.specs import ROOT, contracts
from spring_agents.catchment import mask_area


class AgentRuntimeTests(unittest.TestCase):
    def test_mask_area_is_arithmetic_only_and_flags_edge(self):
        value = mask_area([[False, False, False], [False, True, False], [False, False, False]], 30, 30)
        self.assertEqual(value["area_m2"], 900)
        self.assertEqual(value["area_ha"], 0.09)
        self.assertTrue(value["passes_edge_and_void_screen"])
        clipped = mask_area([[True, False], [False, None]], 30, 30)
        self.assertFalse(clipped["passes_edge_and_void_screen"])

    def test_declared_handoffs_have_producers(self):
        specs = contracts()
        outputs = {output for spec in specs.values() for output in spec["outputs"]}
        missing = {value for spec in specs.values() for value in spec["inputs"] if value not in outputs}
        self.assertEqual(missing, set())

    def test_missing_dem_keeps_catchment_unavailable_and_traceable(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            store, summary = assess({"mode": "catchment", "spring_id": "test-only",
                                     "location": {"latitude": 30.0, "longitude": 78.0, "crs": "EPSG:4326"},
                                     "field_form": {"measurement_date_time": "2026-10-14T10:00:00+05:30",
                                                    "measurement_conditions": "test-only",
                                                    "heavy_rainfall_recent": False,
                                                    "bucket_readings": [
                                         {"volume_L": 2, "time_s": 30},
                                         {"volume_L": 3, "time_s": 45},
                                         {"volume_L": 1, "time_s": 15}]}}, Path(temp))
            profile = store.get("AG-SPR.spring_profile")["payload"]
            self.assertEqual([r["discharge_L_min"] for r in profile["discharge_readings"]], [4.0, 4.0, 4.0])
            self.assertEqual(profile["discharge_protocol"], "protocol-recorded")
            self.assertEqual(store.get("AG-CAT.catchment_geometry")["status"], "unavailable")
            self.assertIsNone(summary["payload"]["area_ha"])
            self.assertIn("AG-CAT.catchment_geometry", store.get("AG-LIN.run_trace")["payload"]["targets"])

    def test_invalid_coordinate_is_not_processed(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            store, _ = assess({"location": {"latitude": "bad", "longitude": 78, "crs": "EPSG:4326"}}, Path(temp))
            self.assertEqual(store.get("AG-SPR.location_evidence")["status"], "unavailable")
            self.assertIsNone(store.get("AG-CAT.outlet_decision")["payload"]["spring_point"])

    def test_springshed_roles_are_connected_without_scheduling_temperature(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            store, summary = assess({"mode": "springshed", "location": {
                "latitude": 30, "longitude": 78, "crs": "EPSG:4326"}}, Path(temp))
            self.assertEqual(store.get("AG-SHD.candidate_recharge_geometries")["status"], "unavailable")
            self.assertIsNone(store.get("AG-TMP.temperature_evidence"))
            self.assertIn("AG-TMP", store.get("AG-LIN.run_trace")["payload"]["not_scheduled_agent_ids"])
            self.assertEqual(summary["payload"]["springshed_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
