import unittest
from decimal import Decimal

from invoice_math import round_money


class RoundMoneyTests(unittest.TestCase):
    def test_rounds_half_cent_up(self) -> None:
        self.assertEqual(round_money("2.675"), Decimal("2.68"))

    def test_returns_two_place_decimal(self) -> None:
        self.assertEqual(round_money(4), Decimal("4.00"))


if __name__ == "__main__":
    unittest.main()
