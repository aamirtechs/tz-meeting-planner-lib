# Good first issues

Ideas for first-time contributors. Each one is small, tested, and
does not change the core validity rules.

1. Add a `--best` flag that prints only the window with the most
   slack, meaning the largest gap to the nearest working-hours edge
   across all participants, with ties broken by earliest start.
2. Support overnight shifts: let a participant declare a shift such
   as 22:00 to 06:00 and define which local day the shift belongs to,
   with tests for a window that crosses midnight.
3. Add a `--format` option that renders windows as a Markdown table
   with one column per participant's local start time.
4. Add optional per-participant blackout dates (for example holidays)
   in the request file, with any window touching a blackout date
   excluded and a test proving it.
