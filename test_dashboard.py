"""Run with: python -m unittest -v. Checks KPI meaning and real UI interactions."""
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from app import filter_orders, generate_orders, metrics, prepare_orders, recommendations


class DashboardChecks(unittest.TestCase):
    def test_seed_and_date_integrity(self):
        first = generate_orders()
        assert_frame_equal(first, generate_orders())
        self.assertEqual(len(first), 1000)
        self.assertTrue(first["order_id"].is_unique)
        self.assertTrue((first["actual_delivery_date"] >= first["order_date"]).all())
        self.assertFalse(first.isna().any().any())

    def test_kpis_include_early_and_exactly_on_time(self):
        # Hand-calculated fixture: early, exactly on time, and two days late.
        source = pd.DataFrame({
            "order_id": ["A", "B", "C"], "order_date": ["2025-01-01"] * 3,
            "promised_delivery_date": ["2025-01-05"] * 3,
            "actual_delivery_date": ["2025-01-04", "2025-01-05", "2025-01-07"],
            "shipping_method": ["Standard"] * 3, "product_category": ["Apparel"] * 3,
            "region": ["North"] * 3, "order_value": [50, 100, 150],
        })
        result = metrics(prepare_orders(source))
        self.assertEqual(result["late_orders"], 1)
        self.assertAlmostEqual(result["on_time_pct"], 200 / 3)
        self.assertAlmostEqual(result["avg_delay_days"], 2 / 3)

    def test_missing_and_duplicate_data_are_rejected(self):
        orders = generate_orders(3)
        with self.assertRaises(ValueError):
            prepare_orders(orders.drop(columns="order_date"))
        with self.assertRaises(ValueError):
            prepare_orders(pd.concat([orders, orders.iloc[[0]]]))

    def test_empty_filter_and_small_sample(self):
        orders = generate_orders()
        empty = filter_orders(orders, [], ["Express"], ["Apparel"], "2025-01-01", "2025-12-31")
        self.assertEqual(metrics(empty)["orders"], 0)
        self.assertIsNone(metrics(empty)["on_time_pct"])
        self.assertEqual(len(recommendations(orders.head(1))), 3)

    def test_app_filter_empty_and_reset(self):
        app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,000")
        app.sidebar.multiselect(key="region").set_value(["East"]).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, f"{(generate_orders()['region'] == 'East').sum():,}")
        app.sidebar.multiselect(key="region").set_value([]).run()
        self.assertTrue(app.warning)
        self.assertEqual(len(app.metric), 0)
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,000")


if __name__ == "__main__":
    unittest.main()
