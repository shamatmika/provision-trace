import unittest

from ecl_engine import (
    ECLValidationError,
    calculate_portfolio_ecl,
    validate_facilities,
    validate_scenarios,
)


SAMPLE = [
    {
        "facility_id": "DEMO-001",
        "stage": 1,
        "exposure": 42000000,
        "pd": 1.2,
        "lgd": 35,
        "horizon_years": 1,
        "discount_rate": 8,
    },
    {
        "facility_id": "DEMO-002",
        "stage": 2,
        "exposure": 38000000,
        "pd": 5.8,
        "lgd": 42,
        "horizon_years": 4,
        "discount_rate": 9,
    },
    {
        "facility_id": "DEMO-003",
        "stage": 3,
        "exposure": 48000000,
        "pd": 12,
        "lgd": 60,
        "horizon_years": 3,
        "discount_rate": 10,
    },
]


class TestECLValidation(unittest.TestCase):
    def test_valid_portfolio_returns_results(self):
        result = calculate_portfolio_ecl(SAMPLE)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["facility_count"], 3)
        self.assertAlmostEqual(result["total_exposure"], 128000000)
        self.assertGreater(result["total_illustrative_ecl"], 0)
        self.assertEqual(result["model_status"], "development_only")

    def test_stage_one_uses_one_year_horizon(self):
        rows = [dict(SAMPLE[0], horizon_years=5)]
        result = calculate_portfolio_ecl(rows)
        self.assertEqual(result["facilities"][0]["horizon_years_used"], 1.0)

    def test_stage_two_uses_supplied_lifetime_horizon(self):
        result = calculate_portfolio_ecl([SAMPLE[1]])
        self.assertEqual(result["facilities"][0]["horizon_years_used"], 4.0)

    def test_rejects_duplicate_facility_ids(self):
        with self.assertRaises(ECLValidationError):
            validate_facilities([SAMPLE[0], SAMPLE[0]])

    def test_rejects_invalid_stage(self):
        with self.assertRaises(ECLValidationError):
            validate_facilities([dict(SAMPLE[0], stage=4)])

    def test_rejects_pd_outside_percent_range(self):
        with self.assertRaises(ECLValidationError):
            validate_facilities([dict(SAMPLE[0], pd=101)])

    def test_rejects_negative_exposure(self):
        with self.assertRaises(ECLValidationError):
            validate_facilities([dict(SAMPLE[0], exposure=-1)])

    def test_rejects_scenario_weights_not_summing_to_one(self):
        with self.assertRaises(ECLValidationError):
            validate_scenarios([
                {"name": "base", "weight": 0.7},
                {"name": "downside", "weight": 0.2},
            ])

    def test_zero_exposure_has_zero_ecl_rate(self):
        result = calculate_portfolio_ecl([dict(SAMPLE[0], exposure=0)])
        self.assertEqual(result["total_illustrative_ecl"], 0)
        self.assertEqual(result["portfolio_ecl_rate_percent"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
