from __future__ import annotations

import unittest

from light.search.calculator_provider import _safe_eval, maybe_calculator_item


class CalculatorProviderTests(unittest.TestCase):
    def test_basic_arithmetic(self) -> None:
        self.assertEqual(_safe_eval("2 + 3 * 4"), "14")

    def test_decimal_result(self) -> None:
        self.assertEqual(_safe_eval("5 / 2"), "2.5")

    def test_division_by_zero_is_rejected(self) -> None:
        self.assertIsNone(_safe_eval("1 / 0"))

    def test_code_execution_is_rejected(self) -> None:
        self.assertIsNone(_safe_eval("__import__('os').system('echo unsafe')"))

    def test_search_item_contains_result(self) -> None:
        item = maybe_calculator_item("(8 + 2) / 5")
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.title, "(8 + 2) / 5 = 2")


if __name__ == "__main__":
    unittest.main()
