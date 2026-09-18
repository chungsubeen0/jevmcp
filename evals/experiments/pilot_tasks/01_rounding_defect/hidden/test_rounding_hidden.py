import unittest
from decimal import Decimal

from invoice_math import round_money


class HiddenRoundMoneyTests(unittest.TestCase):
    def test_negative_tie_rounds_away_from_zero(self) -> None:
        self.assertEqual(round_money("-1.225"), Decimal("-1.23"))

    def test_decimal_input_keeps_decimal_precision(self) -> None:
        value = Decimal("9007199254740993.125")
        self.assertEqual(round_money(value), Decimal("9007199254740993.13"))


if __name__ == "__main__":
    unittest.main()
