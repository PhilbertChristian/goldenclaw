import unittest
from datetime import datetime, timedelta, timezone

from max import core


def _ev(when, tokens):
    return (when, {"input_tokens": tokens}, "claude-test")


class WindowTest(unittest.TestCase):
    t0 = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)

    def test_single_window_start_floored_to_hour(self):
        windows = core.build_windows([_ev(self.t0, 100)])
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["start"].minute, 0)
        self.assertEqual(windows[0]["start"].hour, 9)
        self.assertEqual(windows[0]["end"] - windows[0]["start"], timedelta(hours=5))

    def test_event_inside_window_does_not_open_new_one(self):
        windows = core.build_windows([
            _ev(self.t0, 100),
            _ev(self.t0 + timedelta(hours=4), 50),
        ])
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["total"], 150)

    def test_event_past_window_end_opens_new_window(self):
        # Window is 09:00–14:00 (floored start), so 14:31 is outside it.
        windows = core.build_windows([
            _ev(self.t0, 100),
            _ev(self.t0 + timedelta(hours=5, minutes=1), 50),
        ])
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[1]["start"].hour, 14)

    def test_boundary_event_exactly_at_end_starts_new_window(self):
        end = self.t0.replace(minute=0) + timedelta(hours=5)
        windows = core.build_windows([_ev(self.t0, 1), _ev(end, 1)])
        self.assertEqual(len(windows), 2)

    def test_event_tokens_sums_all_four_categories(self):
        usage = {"input_tokens": 1, "output_tokens": 2,
                 "cache_creation_input_tokens": 3, "cache_read_input_tokens": 4}
        self.assertEqual(core.event_tokens(usage), 10)

    def test_event_tokens_tolerates_missing_and_null_fields(self):
        self.assertEqual(core.event_tokens({"input_tokens": None}), 0)
        self.assertEqual(core.event_tokens({}), 0)


class NightHoursTest(unittest.TestCase):
    def test_night_boundaries(self):
        tz = timezone.utc
        self.assertTrue(core.is_night(datetime(2026, 8, 3, 23, 0, tzinfo=tz)))
        self.assertTrue(core.is_night(datetime(2026, 8, 3, 3, 0, tzinfo=tz)))
        self.assertFalse(core.is_night(datetime(2026, 8, 3, 7, 0, tzinfo=tz)))
        self.assertFalse(core.is_night(datetime(2026, 8, 3, 12, 0, tzinfo=tz)))


if __name__ == "__main__":
    unittest.main()
