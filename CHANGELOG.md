# Changelog

## Unreleased

- `--format` option: `text` (default, unchanged) or `markdown`,
  which renders the windows as a Markdown table with one column
  per participant's local start time. `--format` and `--json`
  are mutually exclusive.

## 1.0.0 (2026-10-31)

- First release.
- Zero-dependency Python CLI and importable library: find meeting
  windows across time zones respecting working hours and workdays.
- IANA time zones via zoneinfo, daylight saving handled by the
  system time zone database.
- Per-participant working hours and workdays, configurable duration,
  step, and search length.
- `--json`, `--check`, `--duration`, `--days`, and `--step` flags.
- 22 passing tests.
