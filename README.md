# tz-meeting-planner-lib

Find meeting windows across time zones, respecting each person's
working hours and workdays. No account, no upload, no dependencies.
Just Python 3 and the standard library (zoneinfo for time zones).

## The problem it solves

A time that looks fine in one time zone can fall outside working
hours in another, and daylight saving changes the overlap twice a
year. This tool takes a JSON description of the team and returns
every window where the whole meeting fits inside everyone's working
hours, in UTC plus each person's local time.

## Input format

A JSON file with participants, a duration, a start date, and a
search length:

```json
{
  "participants": [
    {"name": "Amir", "timezone": "Asia/Karachi",
     "work_start": "14:00", "work_end": "22:00"},
    {"name": "Dana", "timezone": "America/New_York",
     "work_start": "09:00", "work_end": "17:00"}
  ],
  "duration_minutes": 60,
  "start_date": "2026-11-02",
  "days": 5,
  "step_minutes": 60,
  "workdays": [0, 1, 2, 3, 4]
}
```

`work_start` and `work_end` are local times in HH:MM form.
`workdays` uses weekday numbers where 0 is Monday and 6 is Sunday;
it defaults to Monday to Friday and can also be set per participant.
Overnight shifts are rejected, because a shift that crosses midnight
needs an explicit rule for which day it belongs to. Time zone names
are IANA names such as `Asia/Karachi` or `Europe/London`.

## Usage

```sh
python3 tz_meeting_planner.py examples/team.json
python3 tz_meeting_planner.py examples/team.json --json
python3 tz_meeting_planner.py examples/team.json --check
python3 tz_meeting_planner.py examples/team.json --best
python3 tz_meeting_planner.py examples/team.json --duration 30 --step 30
```

`--json` prints the windows as JSON. `--check` exits 1 when no
window fits, so it works as a gate in a script. `--best` prints
only the window with the most slack: the largest gap to the
nearest working-hours edge across all participants, with ties
broken by earliest start. `--duration`, `--days`, and `--step`
override the request file.

## Real output

Running the example team (Amir on a US-hours shift in Karachi,
Dana in New York) over 2026-11-02 to 2026-11-06 gives 15 windows,
three per weekday, all at 14:00, 15:00, and 16:00 UTC:

```text
Participants: Amir, Dana
Duration: 60 minutes
Found 15 window(s):
2026-11-02T14:00:00Z to 2026-11-02T15:00:00Z UTC (Amir 2026-11-02T19:00:00+05:00, Dana 2026-11-02T09:00:00-05:00)
2026-11-02T15:00:00Z to 2026-11-02T16:00:00Z UTC (Amir 2026-11-02T20:00:00+05:00, Dana 2026-11-02T10:00:00-05:00)
2026-11-02T16:00:00Z to 2026-11-02T17:00:00Z UTC (Amir 2026-11-02T21:00:00+05:00, Dana 2026-11-02T11:00:00-05:00)
```

A Saturday search returns no windows, because weekends are not
workdays by default:

```text
Participants: Amir, Dana
Duration: 60 minutes
No window fits every participant's working hours.
```

## Library use

The finder is importable, and it accepts raw JSON-style dicts as
well as parsed requests:

```python
from tz_meeting_planner import find_windows

request = {
    "participants": [
        {"name": "Amir", "timezone": "Asia/Karachi",
         "work_start": "14:00", "work_end": "22:00"},
        {"name": "Dana", "timezone": "America/New_York",
         "work_start": "09:00", "work_end": "17:00"},
    ],
    "duration_minutes": 60,
    "start_date": "2026-11-02",
    "days": 1,
    "step_minutes": 60,
}
windows = find_windows(request)
print(windows[0]["start_utc"])  # 2026-11-02T14:00:00Z
```

## Validity rules

A window is valid only when, for every participant, the whole
meeting falls on a single local calendar day, that day is one of
their workdays, and the local start and end sit inside their
working hours. A window that would cross local midnight is never
returned, even if both days are workdays.

## Tests

```sh
python3 -m unittest discover -s tests
```

22 tests pass, covering overlap math, local time reporting,
weekend exclusion, custom workdays, granularity, validation errors,
and the CLI flags.
