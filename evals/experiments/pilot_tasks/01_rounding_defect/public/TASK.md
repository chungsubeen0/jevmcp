# Fix invoice rounding

`invoice_math.rounding.round_money` occasionally rounds a monetary value in
the wrong direction.

Update the implementation so it:

- accepts a `str`, `int`, `float`, or `Decimal`;
- rounds to exactly two decimal places using decimal `ROUND_HALF_UP`;
- returns a `Decimal`;
- does not perform arithmetic through binary floating-point.

Keep the change localized to `invoice_math/rounding.py` and make all tests
pass.
