#!/usr/bin/env python3
"""Tests for tz_meeting_planner. Run: python3 -m unittest discover -s tests -v."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tz_meeting_planner import (  # noqa: E402
    find_windows, format_text, load_request, parse_hhmm)

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tz_meeting_planner.py")

TEAM = {
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


def request(**overrides):
    data = json.loads(json.dumps(TEAM))
    data.update(overrides)
    if "participants" not in overrides:
        data["participants"] = json.loads(json.dumps(TEAM["participants"]))
    return data


class TestFindWindows(unittest.TestCase):
    def test_overlap_exists_for_karachi_and_new_york(self):
        windows = find_windows(request())
        self.assertTrue(windows)
        hours = [datetime.fromisoformat(
            w["start_utc"].replace("Z", "+00:00")).hour for w in windows]
        self.assertEqual(hours, [14, 15, 16])

    def test_window_local_times_match(self):
        windows = find_windows(request())
        first = windows[0]
        self.assertEqual(first["local_starts"]["Amir"], "2026-11-02T19:00:00+05:00")
        self.assertEqual(first["local_starts"]["Dana"], "2026-11-02T09:00:00-05:00")

    def test_no_window_when_hours_never_overlap(self):
        data = request()
        data["participants"][1]["work_start"] = "00:00"
        data["participants"][1]["work_end"] = "01:00"
        self.assertEqual(find_windows(data), [])

    def test_duration_longer_than_overlap_gives_nothing(self):
        self.assertEqual(find_windows(request(duration_minutes=480)), [])

    def test_weekend_excluded_by_default(self):
        windows = find_windows(request(start_date="2026-11-07", days=1))
        self.assertEqual(windows, [])

    def test_custom_workdays_include_saturday(self):
        data = request(start_date="2026-11-07", days=1)
        for person in data["participants"]:
            person["workdays"] = [5]
        self.assertTrue(find_windows(data))

    def test_window_never_crosses_midnight_locally(self):
        data = request()
        data["participants"][0]["work_start"] = "21:00"
        data["participants"][0]["work_end"] = "22:00"
        data["participants"][1]["work_start"] = "09:00"
        data["participants"][1]["work_end"] = "10:00"
        windows = find_windows(data)
        for window in windows:
            self.assertIn("2026-11-02", window["local_starts"]["Amir"])

    def test_single_participant_gets_whole_workday(self):
        data = request()
        data["participants"] = data["participants"][:1]
        windows = find_windows(data)
        self.assertEqual(len(windows), 8)

    def test_step_controls_granularity(self):
        self.assertEqual(len(find_windows(request(step_minutes=30))), 5)
        self.assertEqual(len(find_windows(request(step_minutes=60))), 3)


class TestBlackouts(unittest.TestCase):
    def test_blackout_removes_windows_on_that_local_date(self):
        data = request()
        data["participants"][1]["blackouts"] = ["2026-11-02"]
        self.assertEqual(find_windows(data), [])

    def test_blackout_removes_only_that_date(self):
        data = request(days=3)
        data["participants"][0]["blackouts"] = ["2026-11-03"]
        windows = find_windows(data)
        self.assertEqual(len(windows), 6)
        for window in windows:
            self.assertFalse(window["start_utc"].startswith("2026-11-03"))

    def test_blackout_outside_search_changes_nothing(self):
        data = request()
        data["participants"][0]["blackouts"] = ["2026-11-06"]
        self.assertEqual(len(find_windows(data)), 3)

    def test_blackout_dates_are_evaluated_in_each_local_zone(self):
        # 01:00-04:00 UTC is 11-03 in Karachi but 11-02 in New York,
        # so each participant's blackout is checked against their own
        # local calendar day.
        data = {
            "participants": [
                {"name": "Amir", "timezone": "Asia/Karachi",
                 "work_start": "06:00", "work_end": "09:00"},
                {"name": "Dana", "timezone": "America/New_York",
                 "work_start": "20:00", "work_end": "23:00"},
            ],
            "duration_minutes": 60,
            "start_date": "2026-11-03",
            "days": 1,
            "step_minutes": 60,
        }
        self.assertEqual(len(find_windows(data)), 3)
        amir = dict(data, participants=[
            dict(data["participants"][0], blackouts=["2026-11-03"]),
            data["participants"][1]])
        self.assertEqual(find_windows(amir), [])
        dana = dict(data, participants=[
            data["participants"][0],
            dict(data["participants"][1], blackouts=["2026-11-02"])])
        self.assertEqual(find_windows(dana), [])
        other_day = dict(data, participants=[
            data["participants"][0],
            dict(data["participants"][1], blackouts=["2026-11-03"])])
        self.assertEqual(len(find_windows(other_day)), 3)

    def test_load_request_accepts_blackouts(self):
        data = request()
        data["participants"][1]["blackouts"] = ["2026-11-02"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            parsed = load_request(path)
        finally:
            os.unlink(path)
        self.assertEqual(parsed["participants"][1]["blackouts"],
                         {date(2026, 11, 2)})
        self.assertEqual(find_windows(parsed), [])

    def test_blackout_rejections(self):
        for bad in (["2026-13-40"], ["not-a-date"], "2026-11-02", [42]):
            data = request()
            data["participants"][0]["blackouts"] = bad
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(data, f)
                path = f.name
            try:
                with self.assertRaises(ValueError):
                    load_request(path)
            finally:
                os.unlink(path)


class TestValidation(unittest.TestCase):
    def test_parse_hhmm_valid(self):
        self.assertEqual(str(parse_hhmm("09:30", "work_start")), "09:30:00")

    def test_parse_hhmm_rejects_bad_forms(self):
        for bad in ("9", "25:00", "09:60", "nine", ""):
            with self.assertRaises(ValueError):
                parse_hhmm(bad, "work_start")

    def test_unknown_timezone_rejected(self):
        data = request()
        data["participants"][0]["timezone"] = "Mars/Olympus"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_request(path)
        finally:
            os.unlink(path)

    def test_overnight_shift_rejected(self):
        data = request()
        data["participants"][0]["work_start"] = "22:00"
        data["participants"][0]["work_end"] = "06:00"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_request(path)
        finally:
            os.unlink(path)

    def test_empty_participants_rejected(self):
        data = request(participants=[])
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_request(path)
        finally:
            os.unlink(path)

    def test_bad_date_rejected(self):
        data = request(start_date="02/11/2026")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_request(path)
        finally:
            os.unlink(path)


class TestCli(unittest.TestCase):
    def run_cli(self, data, *extra):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, CLI, path, *extra],
                capture_output=True, text=True)
        finally:
            os.unlink(path)
        return proc

    def test_text_output_lists_windows(self):
        proc = self.run_cli(TEAM)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Found 3 window(s)", proc.stdout)
        self.assertIn("2026-11-02T14:00:00Z", proc.stdout)

    def test_json_output_parses(self):
        proc = self.run_cli(TEAM, "--json")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["windows"]), 3)

    def test_check_passes_with_windows(self):
        proc = self.run_cli(TEAM, "--check")
        self.assertEqual(proc.returncode, 0)

    def test_check_fails_without_windows(self):
        data = request()
        data["participants"][1]["work_start"] = "00:00"
        data["participants"][1]["work_end"] = "01:00"
        proc = self.run_cli(data, "--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No window fits", proc.stdout)

    def test_duration_override(self):
        proc = self.run_cli(TEAM, "--duration", "30", "--step", "30", "--json")
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["windows"]), 6)

    def test_missing_file_exits_2(self):
        proc = subprocess.run([sys.executable, CLI, "/nonexistent.json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error:", proc.stderr)

    def test_blackout_participant_excluded_via_cli(self):
        data = request()
        data["participants"][0]["blackouts"] = ["2026-11-02"]
        proc = self.run_cli(data, "--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No window fits", proc.stdout)

    def test_format_text_empty(self):
        text = format_text([], request())
        self.assertIn("No window fits", text)


if __name__ == "__main__":
    unittest.main()
