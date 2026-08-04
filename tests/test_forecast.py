import unittest
from datetime import datetime, timedelta, timezone

from goldenclaw import forecast


def _window(percent_used, hours_until_reset, now):
    return {
        "percent_used": percent_used,
        "resets_at": (now + timedelta(hours=hours_until_reset)).isoformat(),
    }


class WeekVerdictTest(unittest.TestCase):
    now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

    def test_waste_when_pace_leaves_big_leftover(self):
        # 3 days elapsed, 10% used → pace projects ~23% at reset → ~77% unused.
        w = _window(10.0, hours_until_reset=96, now=self.now)
        v = forecast.week_verdict(w, now=self.now)
        self.assertEqual(v["verdict"], forecast.WASTE)
        self.assertGreater(v["projected_unused_pct"], forecast.WASTE_LEFTOVER_PCT)

    def test_shortfall_when_pace_crosses_100(self):
        # 1 day elapsed, 40% used → pace projects 280% → wall well before reset.
        w = _window(40.0, hours_until_reset=144, now=self.now)
        v = forecast.week_verdict(w, now=self.now)
        self.assertEqual(v["verdict"], forecast.SHORTFALL)
        self.assertIsNotNone(v["hours_to_wall"])
        self.assertLess(v["hours_to_wall"], 144)

    def test_pace_when_projection_lands_near_full(self):
        # Halfway through the week at 45% → projects 90% → healthy.
        w = _window(45.0, hours_until_reset=84, now=self.now)
        v = forecast.week_verdict(w, now=self.now)
        self.assertEqual(v["verdict"], forecast.PACE)

    def test_no_verdict_without_reset_time(self):
        self.assertIsNone(forecast.week_verdict({"percent_used": 50, "resets_at": None},
                                                now=self.now))

    def test_no_verdict_when_reset_already_passed(self):
        w = _window(50.0, hours_until_reset=-1, now=self.now)
        self.assertIsNone(forecast.week_verdict(w, now=self.now))

    def test_no_verdict_in_first_hour_of_week(self):
        # A week that just reset has no meaningful pace yet.
        w = _window(0.5, hours_until_reset=167.5, now=self.now)
        self.assertIsNone(forecast.week_verdict(w, now=self.now))

    def test_zero_usage_is_waste_not_crash(self):
        w = _window(0.0, hours_until_reset=100, now=self.now)
        v = forecast.week_verdict(w, now=self.now)
        self.assertEqual(v["verdict"], forecast.WASTE)


class EstimateTest(unittest.TestCase):
    def _nights_dir(self, entries):
        import json
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        with open(d / "2026-08-01.jsonl", "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")
        return d

    def test_no_history_means_no_estimate(self):
        import tempfile
        from pathlib import Path
        self.assertIsNone(forecast.estimate_tasks(2, Path(tempfile.mkdtemp()) / "absent"))

    def test_estimate_uses_median_of_real_tasks_only(self):
        d = self._nights_dir([
            {"type": "task", "tokens": 1_000_000},
            {"type": "task", "tokens": 3_000_000},
            {"type": "task", "tokens": 9_000_000},
            {"type": "budget_stop", "spent": 99},        # ignored
            {"type": "task", "tokens": 0},               # ignored: no cost recorded
        ])
        est = forecast.estimate_tasks(2, d)
        self.assertEqual(est["runs_on_record"], 3)
        self.assertEqual(est["per_task_median"], 3_000_000)
        self.assertEqual(est["tonight_median"], 6_000_000)

    def test_zero_tasks_returns_none(self):
        d = self._nights_dir([{"type": "task", "tokens": 1000}])
        self.assertIsNone(forecast.estimate_tasks(0, d))


if __name__ == "__main__":
    unittest.main()
