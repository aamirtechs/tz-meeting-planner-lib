# Changelog

## Unreleased

- Optional per-participant `blackouts` (for example holidays): a
  list of YYYY-MM-DD dates in the participant's own time zone; any
  window falling on one of those dates is excluded.

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
