# Changelog

## Unreleased

- `--best` flag: print only the window with the most slack (largest
  gap to the nearest working-hours edge across all participants),
  ties broken by earliest start.

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
