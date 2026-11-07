#!/usr/bin/env python3
"""Find meeting windows across time zones, respecting working hours.

Input is a JSON file describing the participants and the search:

    {
      "participants": [
        {"name": "Amir", "timezone": "Asia/Karachi",
         "work_start": "14:00", "work_end": "22:00",
         "blackouts": ["2026-11-03"]},
        {"name": "Dana", "timezone": "America/New_York",
         "work_start": "09:00", "work_end": "17:00"}
      ],
      "duration_minutes": 60,
      "start_date": "2026-11-02",
      "days": 5,
      "step_minutes": 30,
      "workdays": [0, 1, 2, 3, 4]
    }

A window is valid when, for every participant, the whole meeting falls
inside that participant's working hours on one of their workdays, in
their own time zone, and does not touch one of their blackout dates
(holidays, optional per participant). Windows are reported in UTC plus
each participant's local start time. Only the Python standard library
is used (zoneinfo for time zones).

Usage:

    python3 tz_meeting_planner.py team.json
    python3 tz_meeting_planner.py team.json --json
    python3 tz_meeting_planner.py team.json --check
    python3 tz_meeting_planner.py team.json --duration 30 --days 3
"""

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_WORKDAYS = [0, 1, 2, 3, 4]


def parse_hhmm(value, field):
    """Parse an HH:MM string into a time, raising ValueError otherwise."""
    try:
        hour_text, minute_text = value.split(":")
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, AttributeError):
        raise ValueError("%s must look like HH:MM, got %r" % (field, value))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("%s must be a real time of day, got %r" % (field, value))
    return time(hour, minute)


def parse_blackouts(values, name):
    """Parse an optional list of YYYY-MM-DD blackout dates into a set."""
    if isinstance(values, str) or not isinstance(values, list):
        raise ValueError(
            "participant %s: blackouts must be a list of YYYY-MM-DD dates" % name)
    parsed = set()
    for value in values:
        try:
            parsed.add(date.fromisoformat(value))
        except (TypeError, ValueError):
            raise ValueError(
                "participant %s: blackout %r must be a YYYY-MM-DD date" % (name, value))
    return parsed


def load_request(path):
    """Load and validate a request JSON file, returning a dict."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("request file must contain a JSON object")
    participants = data.get("participants")
    if not participants or not isinstance(participants, list):
        raise ValueError("request needs a non-empty participants list")
    parsed = []
    for index, person in enumerate(participants):
        if not isinstance(person, dict):
            raise ValueError("participant %d must be an object" % index)
        name = person.get("name", "participant %d" % index)
        tz_name = person.get("timezone")
        if not tz_name:
            raise ValueError("participant %s is missing timezone" % name)
        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            raise ValueError("participant %s has unknown timezone %r" % (name, tz_name))
        start = parse_hhmm(person.get("work_start", "09:00"), "work_start")
        end = parse_hhmm(person.get("work_end", "17:00"), "work_end")
        if end <= start:
            raise ValueError(
                "participant %s: work_end must be after work_start "
                "(overnight shifts are not supported)" % name)
        days = person.get("workdays", data.get("workdays", DEFAULT_WORKDAYS))
        if not days or any(d not in range(7) for d in days):
            raise ValueError("participant %s: workdays must be weekday numbers 0-6" % name)
        blackouts = parse_blackouts(person.get("blackouts", []), name)
        parsed.append({"name": name, "timezone": tz_name,
                       "work_start": start, "work_end": end,
                       "workdays": sorted(set(days)),
                       "blackouts": blackouts})
    duration = data.get("duration_minutes", 60)
    if not isinstance(duration, int) or duration <= 0:
        raise ValueError("duration_minutes must be a positive integer")
    step = data.get("step_minutes", 30)
    if not isinstance(step, int) or step <= 0:
        raise ValueError("step_minutes must be a positive integer")
    start_text = data.get("start_date")
    if not start_text:
        raise ValueError("request needs start_date in YYYY-MM-DD form")
    try:
        start_date = date.fromisoformat(start_text)
    except ValueError:
        raise ValueError("start_date must be YYYY-MM-DD, got %r" % start_text)
    days_count = data.get("days", 5)
    if not isinstance(days_count, int) or days_count <= 0:
        raise ValueError("days must be a positive integer")
    return {"participants": parsed, "duration_minutes": duration,
            "step_minutes": step, "start_date": start_date,
            "days": days_count}


def _normalize_blackouts(values):
    """Coerce a blackout list (YYYY-MM-DD strings, dates, datetimes)
    into a set of dates, matching load_request validation."""
    if not isinstance(values, (list, set, tuple)):
        raise ValueError("blackouts must be a list of YYYY-MM-DD dates")
    parsed = set()
    for value in values:
        if isinstance(value, datetime):
            parsed.add(value.date())
        elif isinstance(value, date):
            parsed.add(value)
        elif isinstance(value, str):
            try:
                parsed.add(date.fromisoformat(value))
            except ValueError:
                raise ValueError("blackout %r must be a YYYY-MM-DD date" % value)
        else:
            raise ValueError("blackout %r must be a YYYY-MM-DD date" % value)
    return parsed


def _inside_work(person, start_utc, end_utc):
    """True when the whole UTC window fits one workday for a person."""
    tz = ZoneInfo(person["timezone"])
    local_start = start_utc.astimezone(tz)
    local_end = end_utc.astimezone(tz)
    if local_start.date() != local_end.date():
        return False
    if local_start.date() in person.get("blackouts", ()):
        return False
    if local_start.weekday() not in person["workdays"]:
        return False
    if local_start.timetz().replace(tzinfo=None) < person["work_start"]:
        return False
    if local_end.timetz().replace(tzinfo=None) > person["work_end"]:
        return False
    return True


def normalize_request(request):
    """Return a copy of a request with dates and times parsed.

    Accepts both load_request output (parsed dates and times) and raw
    JSON-style dicts (string dates and HH:MM times), so library users
    can pass either form.
    """
    data = dict(request)
    start_date = data["start_date"]
    if isinstance(start_date, str):
        data["start_date"] = date.fromisoformat(start_date)
    people = []
    for person in request["participants"]:
        person = dict(person)
        if isinstance(person.get("work_start"), str):
            person["work_start"] = parse_hhmm(person["work_start"], "work_start")
        if isinstance(person.get("work_end"), str):
            person["work_end"] = parse_hhmm(person["work_end"], "work_end")
        person.setdefault("workdays", DEFAULT_WORKDAYS)
        person["blackouts"] = _normalize_blackouts(person.get("blackouts", []))
        people.append(person)
    data["participants"] = people
    return data


def find_windows(request):
    """Return the list of valid windows for a request dict.

    Each window is a dict with UTC start and end in ISO form plus, per
    participant, the local start time in ISO form.
    """
    request = normalize_request(request)
    duration = timedelta(minutes=request["duration_minutes"])
    step = timedelta(minutes=request["step_minutes"])
    search_start = datetime.combine(request["start_date"], time(0, 0),
                                    tzinfo=timezone.utc)
    search_end = search_start + timedelta(days=request["days"])
    windows = []
    cursor = search_start
    while cursor + duration <= search_end:
        end = cursor + duration
        if all(_inside_work(p, cursor, end) for p in request["participants"]):
            window = {"start_utc": cursor.isoformat().replace("+00:00", "Z"),
                      "end_utc": end.isoformat().replace("+00:00", "Z"),
                      "local_starts": {}}
            for person in request["participants"]:
                local = cursor.astimezone(ZoneInfo(person["timezone"]))
                window["local_starts"][person["name"]] = local.isoformat()
            windows.append(window)
        cursor += step
    return windows


def format_text(windows, request):
    """Render windows as plain text, one line per window."""
    lines = []
    names = ", ".join(p["name"] for p in request["participants"])
    lines.append("Participants: %s" % names)
    lines.append("Duration: %d minutes" % request["duration_minutes"])
    if not windows:
        lines.append("No window fits every participant's working hours.")
        return "\n".join(lines) + "\n"
    lines.append("Found %d window(s):" % len(windows))
    for window in windows:
        locals_text = ", ".join(
            "%s %s" % (name, value)
            for name, value in window["local_starts"].items())
        lines.append("%s to %s UTC (%s)" % (
            window["start_utc"], window["end_utc"], locals_text))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Find meeting windows across time zones.")
    parser.add_argument("request", help="JSON request file")
    parser.add_argument("--json", action="store_true",
                        help="print the windows as JSON")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when no window fits")
    parser.add_argument("--duration", type=int, default=None,
                        help="override duration_minutes")
    parser.add_argument("--days", type=int, default=None,
                        help="override days searched")
    parser.add_argument("--step", type=int, default=None,
                        help="override step_minutes")
    args = parser.parse_args(argv)
    try:
        request = load_request(args.request)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    if args.duration is not None:
        if args.duration <= 0:
            print("error: --duration must be positive", file=sys.stderr)
            return 2
        request["duration_minutes"] = args.duration
    if args.days is not None:
        if args.days <= 0:
            print("error: --days must be positive", file=sys.stderr)
            return 2
        request["days"] = args.days
    if args.step is not None:
        if args.step <= 0:
            print("error: --step must be positive", file=sys.stderr)
            return 2
        request["step_minutes"] = args.step
    windows = find_windows(request)
    if args.json:
        print(json.dumps({"windows": windows}, indent=2))
    else:
        print(format_text(windows, request), end="")
    if args.check and not windows:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
