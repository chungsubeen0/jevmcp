# Complete tag normalization

Finish `tag_tools.normalize_tags` and expand its visible regression coverage.

The function must:

- accept any iterable of strings, including a generator;
- trim surrounding whitespace and discard blank values;
- normalize values with `str.casefold()`;
- remove duplicates after normalization while preserving first-seen order;
- raise `ValueError` when `max_tags` is not positive;
- raise `ValueError` instead of truncating when unique tags exceed `max_tags`.

Also add these two methods to `tests/test_tags.py`:

- `test_deduplicates_case_insensitively`
- `test_rejects_non_positive_limit`

Keep the public function signature unchanged and use no third-party packages.
