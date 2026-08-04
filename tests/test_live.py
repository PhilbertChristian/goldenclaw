import unittest

from goldenclaw import live


class NormalizeTest(unittest.TestCase):
    def test_missing_utilization_is_omitted_never_zero(self):
        # The recipe rule: an unknown window must not render as "0% used".
        windows = live._normalize({
            "five_hour": {"utilization": 20.0, "resets_at": "2026-08-05T00:00:00Z"},
            "seven_day_opus": None,
            "seven_day_sonnet": {"utilization": None, "resets_at": None},
            "seven_day": {"resets_at": "2026-08-05T00:00:00Z"},  # no utilization key
        })
        self.assertEqual([w["id"] for w in windows], ["five_hour"])

    def test_used_and_left_are_the_same_axis(self):
        windows = live._normalize({"seven_day": {"utilization": 54.0, "resets_at": None}})
        w = windows[0]
        self.assertEqual(w["percent_used"], 54.0)
        self.assertEqual(w["percent_left"], 46.0)

    def test_left_never_goes_negative(self):
        windows = live._normalize({"seven_day": {"utilization": 120.0, "resets_at": None}})
        self.assertEqual(windows[0]["percent_left"], 0.0)

    def test_extra_usage_never_becomes_a_window(self):
        windows = live._normalize({
            "extra_usage": {"is_enabled": False, "utilization": 5},
            "five_hour": {"utilization": 1.0, "resets_at": None},
        })
        self.assertEqual([w["id"] for w in windows], ["five_hour"])

    def test_known_windows_sort_before_unknown(self):
        windows = live._normalize({
            "mystery_window": {"utilization": 9.0, "resets_at": None},
            "five_hour": {"utilization": 1.0, "resets_at": None},
        })
        self.assertEqual(windows[0]["id"], "five_hour")
        self.assertEqual(windows[-1]["id"], "mystery_window")


class CredentialParseTest(unittest.TestCase):
    def test_nested_oauth_shape(self):
        cred = live._parse_credential(
            '{"claudeAiOauth": {"accessToken": "tok", "expiresAt": 99, '
            '"subscriptionType": "max"}}', "keychain")
        self.assertEqual(cred["token"], "tok")
        self.assertEqual(cred["plan"], "max")
        self.assertEqual(cred["origin"], "keychain")

    def test_root_level_token_fallbacks(self):
        self.assertEqual(live._parse_credential('{"accessToken": "a"}', "file")["token"], "a")
        self.assertEqual(live._parse_credential('{"access_token": "b"}', "file")["token"], "b")

    def test_garbage_returns_none_not_raise(self):
        self.assertIsNone(live._parse_credential("not json", "file"))
        self.assertIsNone(live._parse_credential('"a string"', "file"))
        self.assertIsNone(live._parse_credential('{"claudeAiOauth": {}}', "file"))


class ExtraUsageTest(unittest.TestCase):
    def test_disabled_extra_usage_is_none(self):
        self.assertIsNone(live._extra_usage({"extra_usage": {"is_enabled": False}}))
        self.assertIsNone(live._extra_usage({}))

    def test_enabled_extra_usage_maps_fields(self):
        extra = live._extra_usage({"extra_usage": {
            "is_enabled": True, "used_credits": 3, "monthly_limit": 50, "currency": "USD"}})
        self.assertEqual(extra["used_credits"], 3)
        self.assertEqual(extra["monthly_limit"], 50)


if __name__ == "__main__":
    unittest.main()
