import unittest


class SchemaTests(unittest.TestCase):
    def test_valid_test_design_v1_document(self):
        from embeddedflow.schema import validate_test_design_v1

        data = {
            "schema": "test_design_v1",
            "requirement": "REQ-EXM-FUEL-GAUGE-001",
            "produced_by": "agent_task",
            "produced_at": "2026-04-30T09:30:00Z",
            "review": {"status": "approved"},
            "stimulus": {
                "type": "cansim_sequence",
                "sequences": [{"id": "fuel_low", "signals": [{"name": "iFuelLevel_a", "value": 0}]}],
            },
            "observations": [{"id": "fuel_ring_visual", "type": "visual"}],
            "pass_criteria": [{"id": "visual_fuel_change", "type": "manual_visual"}],
            "automation_plan": {
                "automated": [{"description": "CAN stimulus injection"}],
                "manual": [{"description": "Visual comparison"}],
            },
            "known_gaps": ["Boundary values not tested"],
            "risks": [{"severity": "low", "description": "Timing drift"}],
        }
        self.assertEqual(validate_test_design_v1(data), [])

    def test_missing_required_keys(self):
        from embeddedflow.schema import validate_test_design_v1

        errors = validate_test_design_v1({
            "schema": "test_design_v1",
            "requirement": "REQ-1",
            "observations": [{"id": "obs", "type": "visual"}],
            "pass_criteria": [{"id": "crit", "type": "auto"}],
            "automation_plan": {"automated": [], "manual": []},
        })
        self.assertIn("missing required key: stimulus", errors)

    def test_invalid_types(self):
        from embeddedflow.schema import validate_test_design_v1

        errors = validate_test_design_v1({
            "schema": "test_design_v1",
            "requirement": "REQ-1",
            "stimulus": {"type": "manual"},
            "observations": "visual",
            "pass_criteria": [{"id": "crit", "type": "auto"}],
            "automation_plan": {"automated": [], "manual": []},
        })
        self.assertIn("observations must be a non-empty list", errors)

    def test_unknown_schema_name(self):
        from embeddedflow.schema import validate_schema

        with self.assertRaises(ValueError):
            validate_schema("unknown_v1", {})


if __name__ == "__main__":
    unittest.main()
